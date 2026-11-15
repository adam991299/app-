"""Day and week boundaries for the loss limits (decision D12).

The account's day and week follow Swedish local time (Adam's base, ISK in SEK): a day is
midnight to midnight in Europe/Stockholm and a week starts Monday 00:00 there. Daylight
saving is handled by ``zoneinfo``.
"""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

ACCOUNT_TIMEZONE = ZoneInfo("Europe/Stockholm")


def day_start(now: datetime, tz: ZoneInfo = ACCOUNT_TIMEZONE) -> datetime:
    if now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    local = now.astimezone(tz).date()
    return datetime.combine(local, time(0), tzinfo=tz).astimezone(UTC)


def week_start(now: datetime, tz: ZoneInfo = ACCOUNT_TIMEZONE) -> datetime:
    if now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    local = now.astimezone(tz).date()
    monday = local - timedelta(days=local.weekday())
    return datetime.combine(monday, time(0), tzinfo=tz).astimezone(UTC)
