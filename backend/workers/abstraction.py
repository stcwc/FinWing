"""Abstraction worker (LLD §6.4): Haiku summarizes each unique article once,
then the abstraction is fanned out to every matched TOPIC# feed-index item."""

import json

import anthropic
from botocore.exceptions import ClientError

from app import settings
from app.services.db import content_table, utcnow

ABSTRACTION_SYSTEM = """You are a concise financial news analyst.
Summarize the given headline and excerpt in 2-3 sentences.
Focus on: what happened, which assets or markets are affected, and why it matters.
Do not invent facts not present in the input. Use clear, neutral language."""

_client = None


def client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=settings.anthropic_api_key())
    return _client


def abstract_article(article_id: str) -> bool:
    resp = content_table().get_item(Key={"PK": f"ART#{article_id}", "SK": "META"})
    article = resp.get("Item")
    if article is None or article.get("abstraction"):
        return False  # gone or already done (idempotent)

    msg = client().messages.create(
        model=settings.HAIKU_MODEL,
        max_tokens=150,
        system=[{"type": "text", "text": ABSTRACTION_SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[
            {
                "role": "user",
                "content": f"Headline: {article['title']}\n\nExcerpt: {article.get('excerpt', '(none)')}",
            }
        ],
    )
    abstraction = msg.content[0].text.strip()

    try:
        content_table().update_item(
            Key={"PK": f"ART#{article_id}", "SK": "META"},
            UpdateExpression="SET abstraction = :a, abstractedAt = :ts, abstractionModel = :m",
            ConditionExpression="attribute_not_exists(abstraction)",
            ExpressionAttributeValues={
                ":a": abstraction,
                ":ts": utcnow(),
                ":m": settings.HAIKU_MODEL,
            },
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return False  # raced with another invocation
        raise

    # Fan-out to feed-index items (≤5 matched topics per article)
    for topic_id in article.get("matchedTopicIds", []):
        content_table().update_item(
            Key={"PK": f"TOPIC#{topic_id}", "SK": f"TS#{article['publishedAt']}#{article_id}"},
            UpdateExpression="SET abstraction = :a",
            ExpressionAttributeValues={":a": abstraction},
        )
    return True


def handler(event, context):
    done = 0
    for record in event.get("Records", []):
        body = json.loads(record["body"])
        if abstract_article(body["articleId"]):
            done += 1
    print(json.dumps({"level": "INFO", "abstracted": done}))
