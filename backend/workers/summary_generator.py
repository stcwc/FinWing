"""Daily summary generator (LLD §6.6, §7): fetches the lens's 24h articles
and tracked-asset price moves, picks the asset or news-only prompt variant,
calls Sonnet, and writes the summary (never clobbering user edits)."""

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import anthropic

from app import settings
from app.prompts import (
    SUMMARY_ASSET_SYSTEM,
    SUMMARY_NEWS_ONLY_SYSTEM,
    summary_language_directive,
)
from app.services import db, taxonomy
from workers import prices

_client = None


def client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=settings.anthropic_api_key())
    return _client


# ── Articles ─────────────────────────────────────────────────────


def fetch_articles_window(topic_ids: list[str], start_iso: str, end_iso: str) -> list[dict]:
    """Matched articles for the lens topics within the 24h window ending at the
    summary moment (works for both the live run and historical backfill)."""
    seen: dict[str, dict] = {}
    for tid in topic_ids[: settings.MAX_TOPICS_PER_LENS]:
        for item in db.query_topic_window(tid, start_iso, end_iso, limit=40):
            if item["articleId"] not in seen:
                seen[item["articleId"]] = item
    return sorted(seen.values(), key=lambda i: i["publishedAt"], reverse=True)[:40]


# ── Prompt assembly ──────────────────────────────────────────────


def build_user_turn(lens: dict, articles: list[dict], asset_moves: list[dict],
                    prior: list[dict], date: str, news_only: bool) -> str:
    topic_names = [
        taxonomy.topics().get(t, {}).get("displayName", t) for t in lens["topicIds"]
    ]
    parts = [f'Lens: "{lens["name"]}" | Topics: {", ".join(topic_names)}', ""]

    if not news_only:
        parts.append(f"**24-hour asset moves ({date}):**")
        for m in asset_moves:
            parts.append(f"{m['symbol']}: {m['move']:+.1f}% ({m['open']:.2f} → {m['close']:.2f})")
        parts.append("")

    parts.append("**News abstractions (last 24h, newest first):**")
    if articles:
        for a in articles:
            parts.append(f"[{a['source']}] {a['title']}")
            parts.append(a.get("abstraction") or a.get("excerpt", ""))
            parts.append("---")
    else:
        parts.append("(no matched news in the last 24 hours)")
    parts.append("")

    if prior:
        parts.append("**Prior summaries (for continuity):**")
        for p in prior:
            parts.append(f"{p['date']}: {p['body'][:150]}")
        parts.append("")

    parts.append("Write the news-only daily summary." if news_only else "Write the daily summary.")
    return "\n".join(parts)


def extract_rationale(body: str) -> str:
    for header in ("## Possible Connections", "## What to Watch"):
        if header in body:
            return body.split(header, 1)[1].strip()
    return ""


# ── Entry point ──────────────────────────────────────────────────


def generate(
    user_id: str,
    lens_id: str,
    date: str,
    tz_name: str,
    as_of_iso: str | None = None,
    language: str | None = None,
) -> bool:
    """Generate a per-lens summary for `date`. `as_of_iso` is the window end
    (the summary moment); defaults to now for the live run, or the historical
    5pm-local moment for backfill. `language` (en|zh) controls the output
    language; if None it is read from the user's profile."""
    existing = db.get_summary(user_id, lens_id, date)
    if existing and existing.get("editedByUser"):
        return False

    lens = db.get_lens(user_id, lens_id)
    if lens is None:
        return False

    if language is None:
        profile = db.get_user(user_id)
        language = (profile or {}).get("language", "en")

    as_of = datetime.fromisoformat(as_of_iso) if as_of_iso else datetime.now(timezone.utc)
    window_start = (as_of - timedelta(hours=24)).isoformat()
    articles = fetch_articles_window(lens["topicIds"], window_start, as_of.isoformat())
    if not articles and not lens["trackedAssetIds"]:
        return False  # nothing to say

    week_ago = (as_of - timedelta(days=8)).strftime("%Y-%m-%d")
    prior = [p for p in db.list_summaries(user_id, lens_id, week_ago, date) if p["date"] < date][-3:]

    asset_moves = []
    for asset_id in lens["trackedAssetIds"]:
        move = prices.move_for_date(asset_id, date, tz_name)
        if move:
            asset_moves.append(move)

    news_only = len(asset_moves) == 0
    system = (
        SUMMARY_NEWS_ONLY_SYSTEM if news_only else SUMMARY_ASSET_SYSTEM
    ) + summary_language_directive(language)
    user_turn = build_user_turn(lens, articles, asset_moves, prior, date, news_only)

    resp = client().messages.create(
        model=settings.SONNET_MODEL,
        # Generous ceiling so summaries are never truncated — Chinese uses ~1
        # token/char, so the old 600 cap cut zh summaries off mid-sentence.
        max_tokens=2000,
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user_turn}],
    )
    body = resp.content[0].text.strip()

    moves_attr = [
        {
            "assetId": m["assetId"],
            "symbol": m["symbol"],
            "move": Decimal(str(m["move"])),
            "open": Decimal(str(m["open"])),
            "close": Decimal(str(m["close"])),
        }
        for m in asset_moves
    ]
    return db.put_generated_summary(
        user_id, lens_id, date, body, moves_attr, extract_rationale(body)
    )


def handler(event, context):
    ok = generate(
        event["userId"],
        event["lensId"],
        event["date"],
        event.get("timezone", "UTC"),
        event.get("asOf"),
        event.get("language"),
    )
    print(json.dumps({"level": "INFO", "userId": event["userId"], "lensId": event["lensId"],
                      "date": event["date"], "written": ok}))
