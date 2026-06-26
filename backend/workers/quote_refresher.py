"""Refresh the shared lens-ticker quote cache (EventBridge, every ~15 min).

Unions trackedAssetIds across ALL lenses (deduplicated) and refreshes each
asset's ASSET#<id>/QUOTE item via app.services.quotes. Gated to US regular market
hours so the Twelve Data free-tier budget (8/min, 800/day, shared app-wide) isn't
burned overnight — off-hours the cache keeps its last values and the API falls
back to the daily close. Raising the distinct-symbol count or wanting a faster
refresh needs a different EventBridge rate or a paid Twelve Data plan (see
app/services/quotes.py for the capacity math)."""

import json
from datetime import datetime
from zoneinfo import ZoneInfo

from boto3.dynamodb.conditions import Attr

from app.services import db, quotes
from workers.scheduling import is_market_open


def _market_hours_now() -> bool:
    """True during the US regular equity session on a trading day. The bulk of
    tracked assets are US-listed, and gating the whole run to this window keeps
    the daily credit budget bounded (~26 cycles/day at a 15-min cadence)."""
    et = datetime.now(ZoneInfo("America/New_York"))
    if not is_market_open("equity", et):  # weekday, not a US market holiday
        return False
    mins = et.hour * 60 + et.minute
    return 9 * 60 + 25 <= mins <= 16 * 60 + 5  # ~09:25–16:05 ET (small buffers)


def _all_tracked_asset_ids() -> list[str]:
    table = db.app_table()
    ids: set[str] = set()
    kwargs = {
        "FilterExpression": Attr("SK").begins_with("LENS#"),
        "ProjectionExpression": "trackedAssetIds",
    }
    while True:
        resp = table.scan(**kwargs)
        for item in resp.get("Items", []):
            ids.update(item.get("trackedAssetIds", []) or [])
        if "LastEvaluatedKey" not in resp:
            return sorted(ids)
        kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]


def handler(event, context):
    if not _market_hours_now():
        print(json.dumps({"level": "INFO", "event": "quote_refresh", "skip": "market_closed"}))
        return
    asset_ids = _all_tracked_asset_ids()
    written = quotes.refresh_assets(asset_ids)
    print(json.dumps({"level": "INFO", "event": "quote_refresh",
                      "assets": len(asset_ids), "written": written}))
