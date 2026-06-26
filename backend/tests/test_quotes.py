"""Lens-ticker quotes: Twelve Data /quote parsing, cache refresh/read, fallback."""

from app.services import quotes
from workers import prices
from workers import quote_refresher as qr


class _Resp:
    def __init__(self, payload, status=200):
        self._p = payload
        self.status_code = status

    def json(self):
        return self._p


def test_fetch_quotes_parses_batch(monkeypatch):
    monkeypatch.setenv("TWELVEDATA_API_KEY", "k")
    payload = {
        "NVDA": {"symbol": "NVDA", "close": "194.29", "change": "-4.71",
                 "percent_change": "-2.37", "is_market_open": True},
        "AAPL": {"symbol": "AAPL", "close": "275.11", "change": "-17.97",
                 "percent_change": "-6.13", "is_market_open": True},
    }
    monkeypatch.setattr(quotes.requests, "get", lambda *a, **k: _Resp(payload))
    out = quotes._fetch_quotes(["NVDA", "AAPL"])
    assert out["NVDA"]["price"] == 194.29
    assert out["NVDA"]["change"] == -4.71
    assert out["AAPL"]["percentChange"] == -6.13
    assert out["NVDA"]["marketOpen"] is True


def test_fetch_quotes_parses_single(monkeypatch):
    monkeypatch.setenv("TWELVEDATA_API_KEY", "k")
    payload = {"symbol": "XAU/USD", "close": "4028.1", "change": "27.0",
               "percent_change": "0.67", "is_market_open": True}
    monkeypatch.setattr(quotes.requests, "get", lambda *a, **k: _Resp(payload))
    out = quotes._fetch_quotes(["XAU/USD"])
    assert out["XAU/USD"]["price"] == 4028.1


def test_refresh_and_get_price_and_yield(tables, monkeypatch):
    monkeypatch.setattr(quotes, "_fetch_quotes", lambda syms: {
        "NVDA": {"price": 194.29, "change": -4.71, "percentChange": -2.37, "marketOpen": True}
    })
    monkeypatch.setattr(prices, "move_for_date", lambda aid, d, tz: {
        "assetId": aid, "symbol": "US30Y", "open": 4.81, "close": 4.85, "move": 0.04, "kind": "yield"
    })
    assert quotes.refresh_assets(["NVDA", "US30Y"]) == 2

    got = {q["assetId"]: q for q in quotes.get_quotes(["NVDA", "US30Y"])}
    assert got["NVDA"]["kind"] == "price" and got["NVDA"]["price"] == 194.29
    assert got["NVDA"]["stale"] is False
    assert got["US30Y"]["kind"] == "yield" and got["US30Y"]["price"] == 4.85
    assert got["US30Y"]["change"] == 0.04


def test_get_quotes_cache_miss_falls_back_to_daily(tables, monkeypatch):
    # No QUOTE cache → daily close (price asset reports % change, abs change = close-open).
    monkeypatch.setattr(prices, "move_for_date", lambda aid, d, tz: {
        "assetId": aid, "symbol": "NVDA", "open": 199.0, "close": 194.29, "move": -2.37, "kind": "price"
    })
    got = quotes.get_quotes(["NVDA"])[0]
    assert got["stale"] is True and got["kind"] == "price"
    assert round(got["change"], 2) == -4.71
    assert got["percentChange"] == -2.37


def test_get_quotes_no_data_returns_nulls(tables, monkeypatch):
    monkeypatch.setattr(prices, "move_for_date", lambda *a, **k: None)
    got = quotes.get_quotes(["NVDA"])[0]
    assert got["price"] is None and got["stale"] is True


def test_refresher_skips_when_market_closed(tables, monkeypatch):
    monkeypatch.setattr(qr, "_market_hours_now", lambda: False)
    calls = []
    monkeypatch.setattr(qr.quotes, "refresh_assets", lambda ids: calls.append(ids) or 0)
    qr.handler({}, None)
    assert calls == []  # no upstream work off-hours
