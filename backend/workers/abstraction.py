"""Abstraction worker (LLD §6.4): Haiku summarizes each unique article once, in
English and Chinese, then the abstractions are fanned out to every matched
TOPIC# feed-index item."""

import json
import re

import anthropic
from botocore.exceptions import ClientError

from app import settings
from app.services.db import content_table, utcnow

ABSTRACTION_SYSTEM = """You are a concise financial news analyst.
Given a headline and excerpt, produce a JSON object with exactly these keys:
- "abstraction_en": a 2-3 sentence English summary (what happened, which assets or
  markets are affected, why it matters)
- "abstraction_zh": the same summary in Simplified Chinese
- "title_zh": the headline translated to Simplified Chinese

Do not invent facts not present in the input. Use clear, neutral language.
Output ONLY the JSON object, no surrounding text."""


def _parse_json(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw).strip()
    if not raw.startswith("{"):
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            raw = m.group(0)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}

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
        max_tokens=500,
        system=[{"type": "text", "text": ABSTRACTION_SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[
            {
                "role": "user",
                "content": f"Headline: {article['title']}\n\nExcerpt: {article.get('excerpt', '(none)')}",
            }
        ],
    )
    data = _parse_json(msg.content[0].text)
    abstraction = (data.get("abstraction_en") or "").strip()
    abstraction_zh = (data.get("abstraction_zh") or "").strip()
    title_zh = (data.get("title_zh") or "").strip()
    if not abstraction:
        # Parsing failed — fall back to the raw text as the English abstraction.
        abstraction = msg.content[0].text.strip()

    try:
        content_table().update_item(
            Key={"PK": f"ART#{article_id}", "SK": "META"},
            UpdateExpression=(
                "SET abstraction = :a, abstractionZh = :az, titleZh = :tz, "
                "abstractedAt = :ts, abstractionModel = :m"
            ),
            ConditionExpression="attribute_not_exists(abstraction)",
            ExpressionAttributeValues={
                ":a": abstraction,
                ":az": abstraction_zh,
                ":tz": title_zh,
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
            UpdateExpression="SET abstraction = :a, abstractionZh = :az, titleZh = :tz",
            ExpressionAttributeValues={":a": abstraction, ":az": abstraction_zh, ":tz": title_zh},
        )
    return True


def handler(event, context):
    done = 0
    for record in event.get("Records", []):
        body = json.loads(record["body"])
        if abstract_article(body["articleId"]):
            done += 1
    print(json.dumps({"level": "INFO", "abstracted": done}))
