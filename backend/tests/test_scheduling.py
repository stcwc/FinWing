"""DST handling, non-trading-day logic, feed merge, taxonomy validation."""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.services import db, taxonomy
from workers.scheduling import compute_next_summary_at, is_market_open


def test_next_summary_same_day():
    # 10:00 NY time, pref 17:00 → today 17:00 EDT = 21:00 UTC
    now = datetime(2026, 6, 12, 14, 0, tzinfo=timezone.utc)
    result = compute_next_summary_at("17:00", "America/New_York", now)
    assert result == "2026-06-12T21:00:00+00:00"


def test_next_summary_rolls_to_tomorrow():
    # 18:00 NY time, pref 17:00 → tomorrow
    now = datetime(2026, 6, 12, 22, 0, tzinfo=timezone.utc)
    result = compute_next_summary_at("17:00", "America/New_York", now)
    assert result.startswith("2026-06-13T21:00")


def test_dst_transition_fall_back():
    # US DST ends 2026-11-01: 17:00 EDT (UTC-4) becomes 17:00 EST (UTC-5).
    before = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)
    after = datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)
    assert compute_next_summary_at("17:00", "America/New_York", before).endswith("21:00:00+00:00")
    assert compute_next_summary_at("17:00", "America/New_York", after).endswith("22:00:00+00:00")


def test_market_open_rules():
    sat = datetime(2026, 6, 13, tzinfo=ZoneInfo("America/New_York"))
    fri = datetime(2026, 6, 12, tzinfo=ZoneInfo("America/New_York"))
    juneteenth = datetime(2026, 6, 19, tzinfo=ZoneInfo("America/New_York"))
    assert is_market_open("equity", fri) is True
    assert is_market_open("equity", sat) is False
    assert is_market_open("equity", juneteenth) is False  # NYSE holiday
    # Crypto and FX never close
    assert is_market_open("crypto", sat) is True
    assert is_market_open("fx", sat) is True


def test_merged_feed_dedupes_and_prefers_abstraction(tables):
    table = db.content_table()
    # Same article matched under two topics; one copy carries the abstraction
    for topic, abstraction in (("macro-fed", None), ("cmd-gold", "Gold rose on Fed cut hopes.")):
        item = {
            "PK": f"TOPIC#{topic}",
            "SK": "TS#2026-06-12T10:00:00+00:00#abc123",
            "title": "Fed signals cuts",
            "excerpt": "ex",
            "source": "Reuters",
            "url": "https://example.com/1",
        }
        if abstraction:
            item["abstraction"] = abstraction
        table.put_item(Item=item)

    items, cursor = db.merged_feed(["macro-fed", "cmd-gold"])
    assert len(items) == 1
    assert items[0]["abstraction"] == "Gold rose on Fed cut hopes."
    assert cursor is None


def test_merged_feed_sorts_newest_first(tables):
    table = db.content_table()
    for i, ts in enumerate(["2026-06-12T08:00:00+00:00", "2026-06-12T12:00:00+00:00"]):
        table.put_item(
            Item={
                "PK": "TOPIC#macro-fed",
                "SK": f"TS#{ts}#art{i}",
                "title": f"t{i}",
                "excerpt": "",
                "source": "s",
                "url": f"https://example.com/{i}",
            }
        )
    items, _ = db.merged_feed(["macro-fed"])
    assert [i["articleId"] for i in items] == ["art1", "art0"]


def test_taxonomy_validation():
    assert taxonomy.validate_topic_ids(["macro-fed", "cmd-gold"]) == []
    assert taxonomy.validate_topic_ids(["bogus-topic"]) == ["bogus-topic"]
    assert taxonomy.validate_asset_ids(["NVDA", "BTC"]) == []
    assert taxonomy.validate_asset_ids(["FAKE"]) == ["FAKE"]


def test_asset_suggestions_union_preserves_order():
    suggested = taxonomy.suggested_assets_for_topics(["macro-fed", "cmd-gold"])
    assert suggested[0] == "US10Y"           # first topic's first asset
    assert "XAUUSD" in suggested
    assert len(suggested) == len(set(suggested))  # no duplicates
