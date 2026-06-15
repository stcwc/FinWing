"""Per-user local-time scheduling with DST handling (LLD §6.5).

zoneinfo resolves wall-clock time to UTC per the IANA database, so "17:00
America/New_York" lands correctly on both sides of a DST transition."""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

US_MARKET_HOLIDAYS = {
    # NYSE full-closure days, 2026
    "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25",
    "2026-06-19", "2026-07-03", "2026-09-07", "2026-11-26", "2026-12-25",
    # 2027
    "2027-01-01", "2027-01-18", "2027-02-15", "2027-03-26", "2027-05-31",
    "2027-06-18", "2027-07-05", "2027-09-06", "2027-11-25", "2027-12-24",
}


def compute_next_summary_at(time_pref: str, tz_name: str, now: datetime | None = None) -> str:
    """Next occurrence of time_pref (HH:MM wall clock) in tz_name, as UTC ISO."""
    tz = ZoneInfo(tz_name)
    now_local = (now or datetime.now(timezone.utc)).astimezone(tz)
    h, m = map(int, time_pref.split(":"))
    candidate = now_local.replace(hour=h, minute=m, second=0, microsecond=0)
    if candidate <= now_local:
        candidate += timedelta(days=1)
    return candidate.astimezone(timezone.utc).isoformat()


def is_market_open(asset_class: str, local_date: datetime) -> bool:
    """Crypto and FX trade continuously; everything else follows NYSE days."""
    if asset_class in ("crypto", "fx"):
        return True
    if local_date.weekday() >= 5:
        return False
    return local_date.strftime("%Y-%m-%d") not in US_MARKET_HOLIDAYS
