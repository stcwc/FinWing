"""One-off backfill: add Simplified-Chinese fields to articles that were
abstracted before bilingual support shipped.

Such articles have an English `abstraction` but no `abstractionZh` / `titleZh`.
This script translates the existing English abstraction + title with Haiku,
writes them back to the ART#<id> META item, and fans the Chinese fields out to
the matched TOPIC# feed-index items (same shape the abstraction worker uses).

Idempotent and re-runnable: it only touches items still missing `abstractionZh`.

Run from backend/ with the beta table/region:
    AWS_REGION=us-west-2 FINWING_ENV=beta python scripts/backfill_zh.py [--dry-run]
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import anthropic
from boto3.dynamodb.conditions import Attr
from botocore.exceptions import ClientError

from app import settings
from app.services.db import content_table, utcnow

SYSTEM = """You translate financial news text into Simplified Chinese (简体中文).
You are given an English abstraction and an English headline. Return ONLY a JSON
object with exactly these keys:
- "abstraction_zh": the abstraction translated to Simplified Chinese
- "title_zh": the headline translated to Simplified Chinese
Keep asset symbols, tickers, and numbers as-is. Use neutral, natural language.
Output ONLY the JSON object, no surrounding text."""

_client = None


def client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=settings.anthropic_api_key())
    return _client


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
    quotes — each value is bounded by the start of the next key (or the closing
    brace for the last), so raw quotes inside a value don't terminate it."""
    out = {}
    for i, k in enumerate(keys):
        nxt = f'"{keys[i + 1]}"' if i + 1 < len(keys) else r"\}"
        m = re.search(rf'"{k}"\s*:\s*"(.*?)"\s*,?\s*{nxt}', raw, re.DOTALL)
        if m:
            out[k] = m.group(1).strip().replace('\\"', '"').replace("\\n", "\n")
    return out


def parse_fields(raw: str, keys: list[str]) -> dict:
    """Strict JSON first; fall back to tolerant extraction for malformed blobs."""
    data = _parse_json(raw)
    if all(data.get(k) for k in keys):
        return {k: str(data[k]).strip() for k in keys}
    return _tolerant(raw, keys)


def find_targets() -> list[dict]:
    """ART#<id> META items that have an English abstraction but no Chinese yet."""
    table = content_table()
    flt = (
        Attr("PK").begins_with("ART#")
        & Attr("SK").eq("META")
        & Attr("abstraction").exists()
        & (Attr("abstractionZh").not_exists() | Attr("abstractionZh").eq(""))
    )
    items, kwargs = [], {"FilterExpression": flt}
    while True:
        resp = table.scan(**kwargs)
        items.extend(resp.get("Items", []))
        if "LastEvaluatedKey" not in resp:
            return items
        kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]


def extract_embedded(abstraction_raw: str) -> tuple[str, str, str] | None:
    """Some early articles stored the model's raw JSON blob as `abstraction`
    (the original parse failed). In that case the clean English AND Chinese are
    already inside it — recover (abstraction_en, abstraction_zh, title_zh)."""
    data = parse_fields(abstraction_raw, ["abstraction_en", "abstraction_zh", "title_zh"])
    if data.get("abstraction_en") and data.get("abstraction_zh"):
        return data["abstraction_en"], data["abstraction_zh"], data.get("title_zh", "")
    return None


def translate(abstraction: str, title: str) -> tuple[str, str]:
    for _ in range(2):  # one retry — Haiku occasionally returns non-JSON
        msg = client().messages.create(
            model=settings.HAIKU_MODEL,
            max_tokens=600,
            system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": f"Abstraction: {abstraction}\n\nHeadline: {title}"}],
        )
        data = parse_fields(msg.content[0].text, ["abstraction_zh", "title_zh"])
        if data.get("abstraction_zh"):
            return data["abstraction_zh"], data.get("title_zh", "")
    return "", ""


def backfill_one(item: dict, dry_run: bool) -> bool:
    article_id = item["PK"].split("#", 1)[1]

    # Prefer recovering an embedded blob (fixes the broken English too); else
    # translate the existing clean English abstraction.
    embedded = extract_embedded(item["abstraction"])
    if embedded:
        clean_en, abstraction_zh, title_zh = embedded
    else:
        clean_en = item["abstraction"]
        abstraction_zh, title_zh = translate(item["abstraction"], item.get("title", ""))

    if not abstraction_zh:
        print(json.dumps({"level": "WARN", "articleId": article_id, "skip": "no translation"}))
        return False
    if dry_run:
        print(json.dumps({"level": "DRY", "articleId": article_id, "titleZh": title_zh,
                          "fixedEnglish": bool(embedded)}))
        return True

    # Always (re)write the clean English alongside the Chinese: for embedded-blob
    # articles this replaces the raw JSON; for the rest it's a harmless no-op.
    try:
        content_table().update_item(
            Key={"PK": item["PK"], "SK": "META"},
            UpdateExpression=(
                "SET abstraction = :a, abstractionZh = :az, titleZh = :tz, zhBackfilledAt = :ts"
            ),
            ConditionExpression="attribute_not_exists(abstractionZh) OR abstractionZh = :empty",
            ExpressionAttributeValues={
                ":a": clean_en,
                ":az": abstraction_zh,
                ":tz": title_zh,
                ":ts": utcnow(),
                ":empty": "",
            },
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return False  # already filled in by a concurrent run
        raise

    # Fan out to the matched TOPIC# feed-index items (best-effort per topic).
    for topic_id in item.get("matchedTopicIds", []):
        try:
            content_table().update_item(
                Key={"PK": f"TOPIC#{topic_id}", "SK": f"TS#{item['publishedAt']}#{article_id}"},
                UpdateExpression="SET abstraction = :a, abstractionZh = :az, titleZh = :tz",
                ExpressionAttributeValues={":a": clean_en, ":az": abstraction_zh, ":tz": title_zh},
            )
        except ClientError as e:  # feed-index row may have aged out (TTL)
            print(json.dumps({"level": "WARN", "articleId": article_id,
                              "topicId": topic_id, "error": e.response["Error"]["Code"]}))
    return True


def main():
    dry_run = "--dry-run" in sys.argv
    targets = find_targets()
    print(json.dumps({"level": "INFO", "found": len(targets), "dryRun": dry_run}))
    done = 0
    for item in targets:
        try:
            if backfill_one(item, dry_run):
                done += 1
        except Exception as e:  # noqa: BLE001 — keep going on a single bad article
            print(json.dumps({"level": "ERROR", "pk": item.get("PK"), "error": str(e)}))
    print(json.dumps({"level": "INFO", "backfilled": done, "of": len(targets)}))


if __name__ == "__main__":
    main()
