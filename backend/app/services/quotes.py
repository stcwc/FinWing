"""Live-ish asset quotes for the lens ticker (current price + today's change).

Quotes are refreshed by workers/quote_refresher.py into a shared per-asset cache
(ASSET#<id>/QUOTE) and only READ by the API, so user requests never hit the
upstream provider — the Twelve Data free-tier limit (8 credits/min, 800/day,
1 credit per symbol, shared app-wide) is bounded by the refresher cadence, not by
traffic. Prices come from Twelve Data's /quote endpoint; Treasury yields come from
FRED (reusing workers.prices), which has a separate, generous limit.

Capacity: max distinct Twelve Data symbols app-wide ~= 2 x refresh-interval-min
(800/day budget over ~390 market minutes). Raising symbol count or wanting a
faster refresh means a longer/shorter EventBridge rate or a paid plan."""

import time
from datetime import datetime, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

import requests

from app import settings
from app.services import taxonomy
from app.services.db import content_table, utcnow
from workers import prices

TD_QUOTE = "https://api.twelvedata.com/quote"
QUOTE_TTL_DAYS = 1
QUOTE_TZ = "America/New_York"


def _today(tz_name: str) -> str:
    return datetime.now(timezone.utc).astimezone(ZoneInfo(tz_name)).strftime("%Y-%m-%d")


def _fetch_quotes(td_symbols: list[str]) -> dict[str, dict]:
    """{symbol: {price, change, percentChange, marketOpen}} from Twelve Data /quote.
    Chunks into groups of QUOTE_REFRESH_BATCH to respect the 8 credits/min free
    limit (each symbol is one credit), sleeping between chunks like
    prices._fetch_series. Fail-safe: a missing key or HTTP error yields no data."""
    out: dict[str, dict] = {}
    try:
        key = settings.twelvedata_api_key()
    except Exception:  # noqa: BLE001 — key not configured
        return out
    batch = settings.QUOTE_REFRESH_BATCH
    chunks = [td_symbols[i:i + batch] for i in range(0, len(td_symbols), batch)]
    for i, chunk in enumerate(chunks):
        if i > 0:
            time.sleep(8)  # free tier: 8 requests/minute
        try:
            resp = requests.get(
                TD_QUOTE, params={"symbol": ",".join(chunk), "apikey": key}, timeout=15
            )
        except requests.RequestException:
            continue
        if resp.status_code != 200:
            continue
        data = resp.json()
        # A single-symbol request returns the quote object directly (it has a
        # "symbol" key); a batch returns {symbol: quote}. Normalize both.
        rows = [data] if "symbol" in data else [v for v in data.values() if isinstance(v, dict)]
        for row in rows:
            if row.get("status") == "error" or not row.get("close"):
                continue
            try:
                out[row["symbol"]] = {
                    "price": float(row["close"]),
                    "change": float(row.get("change") or 0),
                    "percentChange": float(row.get("percent_change") or 0),
                    "marketOpen": bool(row.get("is_market_open", False)),
                }
            except (ValueError, TypeError, KeyError):
                continue
    return out


def _put_quote(asset_id: str, symbol: str, price: float, change: float,
               pct: float, kind: str, market_open: bool) -> None:
    content_table().put_item(
        Item={
            "PK": f"ASSET#{asset_id}",
            "SK": "QUOTE",
            "symbol": symbol,
            "price": Decimal(str(round(price, 4))),
            "change": Decimal(str(round(change, 4))),
            "percentChange": Decimal(str(round(pct, 4))),
            "kind": kind,
            "marketOpen": market_open,
            "fetchedAt": utcnow(),
            "ttl": int(time.time()) + QUOTE_TTL_DAYS * 86400,
        }
    )


def refresh_assets(asset_ids: list[str]) -> int:
    """Fetch fresh quotes for the given assets and write them to the cache.
    Prices via Twelve Data /quote; yields via FRED (workers.prices). Returns the
    number of assets written."""
    assets = taxonomy.assets()
    td_map: dict[str, tuple[str, dict]] = {}  # twelveDataSymbol -> (assetId, asset)
    yields: list[tuple[str, dict]] = []
    for aid in asset_ids:
        a = assets.get(aid)
        if not a or not a.get("hasPriceFeed"):
            continue
        if a.get("fredSeries") and a.get("assetClass") == "bond":
            yields.append((aid, a))
        elif a.get("twelveDataSymbol"):
            td_map[a["twelveDataSymbol"]] = (aid, a)

    written = 0
    if td_map:
        quotes = _fetch_quotes(list(td_map))
        for sym, (aid, a) in td_map.items():
            q = quotes.get(sym)
            if not q:
                continue
            _put_quote(aid, a["symbol"], q["price"], q["change"],
                       q["percentChange"], "price", q["marketOpen"])
            written += 1

    today = _today(QUOTE_TZ)
    for aid, a in yields:
        mv = prices.move_for_date(aid, today, QUOTE_TZ)
        if not mv:
            continue
        # Yield: price = today's level (%), change = day-over-day pp move.
        _put_quote(aid, a["symbol"], mv["close"], mv["move"], 0.0, "yield", True)
        written += 1
    return written


def get_quotes(asset_ids: list[str]) -> list[dict]:
    """Read the cached quote for each asset. On a cache miss, fall back to the
    latest daily close (via the daily price/yield cache) so the first load before
    the refresher runs still shows a value, flagged stale."""
    assets = taxonomy.assets()
    today = _today(QUOTE_TZ)
    out: list[dict] = []
    for aid in asset_ids:
        a = assets.get(aid)
        if not a:
            continue
        item = content_table().get_item(
            Key={"PK": f"ASSET#{aid}", "SK": "QUOTE"}
        ).get("Item")
        if item:
            out.append({
                "assetId": aid,
                "symbol": item["symbol"],
                "name": a.get("name", aid),
                "price": float(item["price"]),
                "change": float(item["change"]),
                "percentChange": float(item["percentChange"]),
                "kind": item.get("kind", "price"),
                "marketOpen": bool(item.get("marketOpen", False)),
                "asOf": item.get("fetchedAt"),
                "stale": False,
            })
            continue
        # Cache miss → latest daily close (cached; only the never-summarized edge
        # case hits upstream). Yields report a pp change, prices a % change.
        mv = prices.move_for_date(aid, today, QUOTE_TZ) if a.get("hasPriceFeed") else None
        if mv:
            is_yield = mv.get("kind") == "yield"
            out.append({
                "assetId": aid,
                "symbol": a["symbol"],
                "name": a.get("name", aid),
                "price": float(mv["close"]),
                "change": float(mv["move"]) if is_yield else float(mv["close"]) - float(mv["open"]),
                "percentChange": 0.0 if is_yield else float(mv["move"]),
                "kind": "yield" if is_yield else "price",
                "marketOpen": False,
                "asOf": None,
                "stale": True,
            })
        else:
            out.append({
                "assetId": aid, "symbol": a["symbol"], "name": a.get("name", aid),
                "price": None, "change": None, "percentChange": None,
                "kind": "price", "marketOpen": False, "asOf": None, "stale": True,
            })
    return out
