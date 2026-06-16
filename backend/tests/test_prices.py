"""Twelve Data price-move logic (HTTP mocked)."""

from workers import prices


def test_move_on_computes_pct():
    series = {"2026-06-10": 100.0, "2026-06-11": 110.0}
    assert prices._move_on(series, "2026-06-11") == (100.0, 110.0, 10.0)


def test_move_on_no_prior_bar_returns_none():
    assert prices._move_on({"2026-06-11": 110.0}, "2026-06-11") is None


def test_move_on_falls_back_to_latest_prior_bar():
    # A weekend/holiday date with no bar uses the most recent bar on/before it.
    series = {"2026-06-10": 100.0, "2026-06-11": 100.0, "2026-06-12": 105.0}
    assert prices._move_on(series, "2026-06-13") == (100.0, 105.0, 5.0)  # Sat → Fri's bar


def test_moves_for_dates_crypto_and_caching(tables, monkeypatch):
    series = {"2026-06-10": 100.0, "2026-06-11": 110.0, "2026-06-12": 121.0}
    monkeypatch.setattr(prices, "_fetch_series", lambda sym, outputsize: series)
    out = prices.moves_for_dates("BTC", ["2026-06-11", "2026-06-12"], "America/New_York")
    assert out["2026-06-11"]["move"] == 10.0
    assert out["2026-06-12"]["move"] == 10.0

    # Second call must hit the cache (fetch now returns nothing).
    monkeypatch.setattr(prices, "_fetch_series", lambda sym, outputsize: {})
    cached = prices.moves_for_dates("BTC", ["2026-06-11"], "America/New_York")
    assert cached["2026-06-11"]["move"] == 10.0


def test_moves_for_dates_skips_market_closed_for_equity(tables, monkeypatch):
    monkeypatch.setattr(
        prices, "_fetch_series", lambda sym, outputsize: {"2026-06-11": 100.0, "2026-06-12": 105.0}
    )
    # 2026-06-13 is a Saturday → equities closed → no move.
    assert prices.moves_for_dates("AAPL", ["2026-06-13"], "America/New_York") == {}
    # Friday 2026-06-12 is open → move computed.
    out = prices.moves_for_dates("AAPL", ["2026-06-12"], "America/New_York")
    assert out["2026-06-12"]["move"] == 5.0


def test_moves_for_dates_no_price_feed_asset(tables):
    # US10Y has hasPriceFeed: false.
    assert prices.moves_for_dates("US10Y", ["2026-06-12"], "America/New_York") == {}
