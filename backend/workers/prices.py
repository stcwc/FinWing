"""Asset price moves via Twelve Data daily OHLC (live + historical).

One time_series call returns many days at once, so a multi-day backfill costs a
single request per asset. Moves are cached per asset per date (PRICE#<date>,
7-day TTL) and reused across users and lenses."""

import time
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import requests

from app import settings
from app.services import taxonomy
from app.services.db import content_table, utcnow
from workers.scheduling import is_market_open

TD_TIME_SERIES = "https://api.twelvedata.com/time_series"


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


def _move_on(series: dict[str, float], date_str: str) -> tuple[float, float, float] | None:
    """(reference_close, close, move%) for date_str using the prior bar as the
    reference. Returns None if there is no bar on/before the date or no prior
    bar to compare against."""
    if not series:
        return None
    dates = sorted(series)
    on_or_before = [d for d in dates if d <= date_str]
    if not on_or_before:
        return None
    idx = dates.index(on_or_before[-1])
    if idx == 0:
        return None
    close, ref = series[dates[idx]], series[dates[idx - 1]]
    if not ref:
        return None
    return ref, close, round((close - ref) / ref * 100, 2)


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
            "fetchedAt": utcnow(),
            "ttl": int(time.time()) + settings.PRICE_CACHE_TTL_DAYS * 86400,
        }
    )


def moves_for_dates(asset_id: str, date_strs: list[str], tz_name: str) -> dict[str, dict]:
    """Return {date_str: move_record} for the dates that have price data. Skips
    market-closed days for non-24/7 asset classes. Fetches the daily series once
    for any uncached dates."""
    asset = taxonomy.assets().get(asset_id)
    if not asset or not asset.get("hasPriceFeed") or not asset.get("twelveDataSymbol"):
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
        # Enough bars to cover the oldest requested date plus a reference bar.
        span = (datetime.now(tz).date() - min(datetime.strptime(d, "%Y-%m-%d").date() for d in missing)).days
        series = _fetch_series(asset["twelveDataSymbol"], outputsize=max(span + 5, 10))
        for d in missing:
            mv = _move_on(series, d)
            if mv:
                ref, close, move = mv
                rec = {"assetId": asset_id, "symbol": asset["symbol"], "open": ref, "close": close, "move": move}
                _put_cache(asset_id, d, rec)
                result[d] = rec
    return result


def move_for_date(asset_id: str, date_str: str, tz_name: str) -> dict | None:
    """Single-date convenience wrapper (live daily summary)."""
    return moves_for_dates(asset_id, [date_str], tz_name).get(date_str)
