"""Asset price moves via Twelve Data daily OHLC, plus Treasury yields via FRED
(live + historical).

One time_series / observations call returns many days at once, so a multi-day
backfill costs a single request per asset. Moves are cached per asset per date
(PRICE#<date>, 7-day TTL) and reused across users and lenses.

Equities/FX/commodities report a percentage price change; yields (assetClass
"bond" with a fredSeries) report a percentage-point change in the rate. The move
record carries `kind` ("price" | "yield") so the summary and email render the
right units."""

import time
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import requests

from app import settings
from app.services import taxonomy
from app.services.db import content_table, utcnow
from workers.scheduling import is_market_open

TD_TIME_SERIES = "https://api.twelvedata.com/time_series"
FRED_OBSERVATIONS = "https://api.stlouisfed.org/fred/series/observations"


def _fetch_series(td_symbol: str, outputsize: int) -> dict[str, float]:
    """{YYYY-MM-DD: close} for the most recent `outputsize` daily bars, or {}.
    Retries once on a free-tier rate-limit (429/code 429)."""
    for attempt in range(2):
        try:
            resp = requests.get(
                TD_TIME_SERIES,
                params={
                    "symbol": td_symbol,
                    "interval": "1day",
                    "outputsize": outputsize,
                    "apikey": settings.twelvedata_api_key(),
                },
                timeout=15,
            )
        except requests.RequestException:
            return {}
        if resp.status_code == 429:
            if attempt == 0:
                time.sleep(8)  # free tier: 8 requests/minute
                continue
            return {}
        if resp.status_code != 200:
            return {}
        data = resp.json()
        if data.get("code") == 429 and attempt == 0:
            time.sleep(8)
            continue
        if data.get("status") != "ok":
            return {}
        return {
            v["datetime"][:10]: float(v["close"])
            for v in data.get("values", [])
            if v.get("close")
        }
    return {}


def _fetch_fred_series(series_id: str, start: str, end: str) -> dict[str, float]:
    """{YYYY-MM-DD: value} for a FRED series over [start, end], or {}. FRED marks
    non-publication days (holidays) with a "." value, which we drop. Fail-safe: a
    missing API key just yields no data (yields stay untracked) rather than
    breaking summary generation."""
    try:
        api_key = settings.fred_api_key()
    except Exception:  # noqa: BLE001 — SSM param not set yet
        return {}
    try:
        resp = requests.get(
            FRED_OBSERVATIONS,
            params={
                "series_id": series_id,
                "api_key": api_key,
                "file_type": "json",
                "observation_start": start,
                "observation_end": end,
            },
            timeout=15,
        )
    except requests.RequestException:
        return {}
    if resp.status_code != 200:
        return {}
    return {
        o["date"]: float(o["value"])
        for o in resp.json().get("observations", [])
        if o.get("value") not in (None, ".", "")
    }


def _bars_on(series: dict[str, float], date_str: str) -> tuple[float, float] | None:
    """(reference, value) for date_str using the prior bar as the reference.
    Returns None if there is no bar on/before the date or no prior bar to compare
    against."""
    if not series:
        return None
    dates = sorted(series)
    on_or_before = [d for d in dates if d <= date_str]
    if not on_or_before:
        return None
    idx = dates.index(on_or_before[-1])
    if idx == 0:
        return None
    ref = series[dates[idx - 1]]
    if not ref:
        return None
    return ref, series[dates[idx]]


def _get_cache(asset_id: str, date_str: str) -> dict | None:
    item = content_table().get_item(
        Key={"PK": f"ASSET#{asset_id}", "SK": f"PRICE#{date_str}"}
    ).get("Item")
    if not item:
        return None
    return {
        "assetId": asset_id,
        "symbol": item["symbol"],
        "open": float(item["open"]),
        "close": float(item["close"]),
        "move": float(item["move"]),
        "kind": item.get("kind", "price"),
    }


def _put_cache(asset_id: str, date_str: str, rec: dict) -> None:
    content_table().put_item(
        Item={
            "PK": f"ASSET#{asset_id}",
            "SK": f"PRICE#{date_str}",
            "symbol": rec["symbol"],
            "open": Decimal(str(rec["open"])),
            "close": Decimal(str(rec["close"])),
            "move": Decimal(str(rec["move"])),
            "kind": rec.get("kind", "price"),
            "fetchedAt": utcnow(),
            "ttl": int(time.time()) + settings.PRICE_CACHE_TTL_DAYS * 86400,
        }
    )


def moves_for_dates(asset_id: str, date_strs: list[str], tz_name: str) -> dict[str, dict]:
    """Return {date_str: move_record} for the dates that have price data. Skips
    market-closed days for non-24/7 asset classes. Fetches the daily series once
    for any uncached dates."""
    asset = taxonomy.assets().get(asset_id)
    if not asset or not asset.get("hasPriceFeed"):
        return {}
    if asset.get("fredSeries"):
        provider = "fred"
    elif asset.get("twelveDataSymbol"):
        provider = "td"
    else:
        return {}
    tz = ZoneInfo(tz_name)
    asset_class = asset["assetClass"]

    # Only consider dates where the market trades for this asset class.
    eligible = [
        d
        for d in date_strs
        if is_market_open(asset_class, datetime.strptime(d, "%Y-%m-%d").replace(tzinfo=tz))
    ]
    if not eligible:
        return {}

    result, missing = {}, []
    for d in eligible:
        cached = _get_cache(asset_id, d)
        if cached:
            result[d] = cached
        else:
            missing.append(d)

    if missing:
        oldest = min(datetime.strptime(d, "%Y-%m-%d").date() for d in missing)
        if provider == "fred":
            # Pad the start so the prior trading day (the reference bar) is in range.
            start = (oldest - timedelta(days=10)).strftime("%Y-%m-%d")
            end = datetime.now(tz).date().strftime("%Y-%m-%d")
            series = _fetch_fred_series(asset["fredSeries"], start, end)
            kind = "yield"
        else:
            # Enough bars to cover the oldest requested date plus a reference bar.
            span = (datetime.now(tz).date() - oldest).days
            series = _fetch_series(asset["twelveDataSymbol"], outputsize=max(span + 5, 10))
            kind = "price"
        for d in missing:
            bars = _bars_on(series, d)
            if not bars:
                continue
            ref, close = bars
            # Yields move in percentage points; everything else in % change.
            move = round(close - ref, 2) if kind == "yield" else round((close - ref) / ref * 100, 2)
            rec = {"assetId": asset_id, "symbol": asset["symbol"],
                   "open": ref, "close": close, "move": move, "kind": kind}
            _put_cache(asset_id, d, rec)
            result[d] = rec
    return result


def move_for_date(asset_id: str, date_str: str, tz_name: str) -> dict | None:
    """Single-date convenience wrapper (live daily summary)."""
    return moves_for_dates(asset_id, [date_str], tz_name).get(date_str)
