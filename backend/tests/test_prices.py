"""Price-move logic for Twelve Data prices and FRED yields (HTTP mocked)."""

from workers import prices


def test_bars_on_returns_ref_and_value():
    series = {"2026-06-10": 100.0, "2026-06-11": 110.0}
    assert prices._bars_on(series, "2026-06-11") == (100.0, 110.0)


def test_bars_on_no_prior_bar_returns_none():
    assert prices._bars_on({"2026-06-11": 110.0}, "2026-06-11") is None


def test_bars_on_falls_back_to_latest_prior_bar():
    # A weekend/holiday date with no bar uses the most recent bar on/before it.
    series = {"2026-06-10": 100.0, "2026-06-11": 100.0, "2026-06-12": 105.0}
    assert prices._bars_on(series, "2026-06-13") == (100.0, 105.0)  # Sat → Fri's bar


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


def test_moves_for_dates_unknown_asset(tables):
    # An asset id not in the catalog yields no moves.
    assert prices.moves_for_dates("NOPE", ["2026-06-12"], "America/New_York") == {}


def test_moves_for_dates_yield_via_fred_reports_percentage_points(tables, monkeypatch):
    # US30Y (assetClass bond, fredSeries DGS30) → move is the pp change, kind "yield".
    series = {"2026-06-11": 4.81, "2026-06-12": 4.85}
    monkeypatch.setattr(prices, "_fetch_fred_series", lambda sid, start, end: series)
    out = prices.moves_for_dates("US30Y", ["2026-06-12"], "America/New_York")
    rec = out["2026-06-12"]
    assert rec["kind"] == "yield"
    assert rec["move"] == 0.04  # 4.85 - 4.81 percentage points, not a % change
    assert rec["open"] == 4.81 and rec["close"] == 4.85
