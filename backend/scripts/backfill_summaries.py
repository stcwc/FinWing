"""One-off backfill: regenerate daily summaries for dates that were missed
while the generator was crashing (KeyError: 'SK', 2026-06-19 .. 2026-06-22).

Calls summary_generator.generate() directly — NOT the per-user handler — so it
writes summaries without sending the digest email (we don't want four stale
emails per user for past days). The write is conditional and skips any summary
the user has hand-edited, so this is idempotent and re-runnable.

For each due date, the 24h window ends at the user's summary time (summaryTimePref,
local), matching what the live 5pm run would have produced that day.

Run from backend/ with the beta table/region:
    AWS_REGION=us-west-2 FINWING_ENV=beta python scripts/backfill_summaries.py [--dry-run]
"""

import json
import os
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services import db
from workers import summary_generator as sg

DATES = ["2026-06-19", "2026-06-20", "2026-06-21", "2026-06-22"]


def list_user_profiles() -> list[dict]:
    table = db.app_table()
    items, kwargs = [], {
        "FilterExpression": "SK = :p",
        "ExpressionAttributeValues": {":p": "PROFILE"},
    }
    while True:
        resp = table.scan(**kwargs)
        items.extend(resp.get("Items", []))
        if "LastEvaluatedKey" not in resp:
            return items
        kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]


def as_of_for(date: str, time_pref: str, tz_name: str) -> str:
    """The summary moment (window end) for `date`: wall-clock time_pref in the
    user's timezone, as UTC ISO — DST-correct via zoneinfo."""
    h, m = map(int, time_pref.split(":"))
    y, mo, d = map(int, date.split("-"))
    local = datetime(y, mo, d, h, m, tzinfo=ZoneInfo(tz_name))
    return local.astimezone(timezone.utc).isoformat()


def main():
    dry_run = "--dry-run" in sys.argv
    profiles = list_user_profiles()
    print(json.dumps({"level": "INFO", "users": len(profiles), "dates": DATES, "dryRun": dry_run}))

    written = 0
    for profile in profiles:
        user_id = profile["PK"].split("#", 1)[1]
        tz_name = profile.get("timezone", "America/Los_Angeles")
        time_pref = profile.get("summaryTimePref", "17:00")
        language = profile.get("language", "en")
        lenses = db.list_lenses(user_id)

        for date in DATES:
            as_of = as_of_for(date, time_pref, tz_name)
            for lens in lenses:
                lens_id = lens["lensId"]
                if dry_run:
                    print(json.dumps({"level": "DRY", "userId": user_id,
                                      "lensId": lens_id, "date": date, "asOf": as_of}))
                    continue
                try:
                    section = sg.generate(user_id, lens_id, date, tz_name,
                                          as_of_iso=as_of, language=language)
                except Exception as e:  # noqa: BLE001 — keep going past one bad lens
                    print(json.dumps({"level": "ERROR", "userId": user_id,
                                      "lensId": lens_id, "date": date, "error": str(e)}))
                    continue
                if section:
                    written += 1
                    print(json.dumps({"level": "OK", "userId": user_id, "lensId": lens_id,
                                      "date": date, "lensName": section["lensName"]}))
                else:
                    print(json.dumps({"level": "SKIP", "userId": user_id, "lensId": lens_id,
                                      "date": date, "reason": "no-op/nothing-to-say/edited"}))
    print(json.dumps({"level": "INFO", "summariesWritten": written}))


if __name__ == "__main__":
    main()
