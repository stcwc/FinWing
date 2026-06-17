"""Backfill the last N daily summaries for a newly created lens.

Invoked asynchronously from POST /lenses. News comes from the 30-day feed-index
retention; prices from Twelve Data historical OHLC. Prices are pre-warmed once
per asset (one request covering all days) to stay within the free-tier rate
limit, then summaries are generated oldest-first so each can reference the
previous day for continuity."""

import json
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app import settings
from app.services import db
from workers import prices, summary_generator


def handler(event, context):
    user_id = event["userId"]
    lens_id = event["lensId"]

    profile = db.get_user(user_id)
    lens = db.get_lens(user_id, lens_id)
    if profile is None or lens is None:
        return

    tz_name = profile.get("timezone", "America/Los_Angeles")
    pref = profile.get("summaryTimePref", "17:00")
    language = profile.get("language", "en")
    tz = ZoneInfo(tz_name)
    h, m = map(int, pref.split(":"))
    now_local = datetime.now(tz)
    today = now_local.date()

    # Previous N days (today's summary is produced by the scheduler at 5pm).
    dates = [today - timedelta(days=i) for i in range(1, settings.BACKFILL_DAYS + 1)]
    date_strs = [d.strftime("%Y-%m-%d") for d in dates]

    # Pre-warm the price cache: one series fetch per tracked asset covers every
    # backfill day and caches each.
    for asset_id in lens.get("trackedAssetIds", []):
        try:
            prices.moves_for_dates(asset_id, date_strs, tz_name)
        except Exception as e:  # noqa: BLE001 — best-effort; falls back to news-only
            print(json.dumps({"level": "WARN", "asset": asset_id, "error": str(e)}))

    written = 0
    for d in sorted(dates):  # oldest first for continuity
        as_of_local = datetime(d.year, d.month, d.day, h, m, tzinfo=tz)
        if as_of_local > now_local:
            continue
        date_str = d.strftime("%Y-%m-%d")
        as_of_iso = as_of_local.astimezone(timezone.utc).isoformat()
        try:
            if summary_generator.generate(
                user_id, lens_id, date_str, tz_name, as_of_iso, language
            ):
                written += 1
        except Exception as e:  # noqa: BLE001 — one bad day shouldn't abort the rest
            print(json.dumps({"level": "WARN", "date": date_str, "error": str(e)}))

    print(json.dumps({"level": "INFO", "userId": user_id, "lensId": lens_id, "backfilled": written}))
