"""Abstraction worker (LLD §6.4): Haiku summarizes each unique article once, in
English and Chinese, then the abstractions are fanned out to every matched
TOPIC# feed-index item."""

import json
import re

import anthropic
from botocore.exceptions import ClientError

from app import settings
from app.prompts import ABSTRACTION_SYSTEM
from app.services import usage
from app.services.db import content_table, utcnow


ABSTRACTION_KEYS = ["abstraction_en", "abstraction_zh", "title_zh"]


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


def _tolerant(raw: str, keys: list[str]) -> dict:
    """Extract string fields even when the JSON is malformed by unescaped inner
    quotes — Haiku often emits Chinese terms in raw double-quotes (e.g. "山寨季"),
    which breaks json.loads. Each value is bounded by the start of the next key
    (or the closing brace for the last), so raw quotes inside a value don't
    terminate it. Order-dependent: `keys` must match the emitted key order."""
    out = {}
    for i, k in enumerate(keys):
        nxt = f'"{keys[i + 1]}"' if i + 1 < len(keys) else r"\}"
        m = re.search(rf'"{k}"\s*:\s*"(.*?)"\s*,?\s*{nxt}', raw, re.DOTALL)
        if m:
            out[k] = m.group(1).strip().replace('\\"', '"').replace("\\n", "\n")
    return out


def parse_fields(raw: str, keys: list[str]) -> dict:
    """Strict JSON first; fall back to tolerant regex extraction for the
    malformed-inner-quote blobs strict parsing rejects."""
    data = _parse_json(raw)
    if all(data.get(k) for k in keys):
        return {k: str(data[k]).strip() for k in keys}
    return _tolerant(raw, keys)

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
    usage.log_usage("abstraction", settings.HAIKU_MODEL, msg, articleId=article_id)
    data = parse_fields(msg.content[0].text, ABSTRACTION_KEYS)
    abstraction = (data.get("abstraction_en") or "").strip()
    abstraction_zh = (data.get("abstraction_zh") or "").strip()
    title_zh = (data.get("title_zh") or "").strip()
    if not abstraction:
        # Even tolerant parsing failed — fall back to the clean article excerpt,
        # never the raw model blob (which would render as JSON in the feed).
        abstraction = (article.get("excerpt") or "").strip() or article["title"]

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
        try:
            body = json.loads(record["body"])
        except (json.JSONDecodeError, KeyError):
            print(json.dumps({"level": "WARN", "skip": "malformed message"}))
            continue  # one bad message must not fail the whole batch
        if abstract_article(body["articleId"]):
            done += 1
    print(json.dumps({"level": "INFO", "abstracted": done}))
