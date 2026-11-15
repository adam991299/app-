"""Exchange sessions from ``exchange_calendars`` (holidays, half days, daylight saving).

Everything is stored and compared in UTC (spec §2). Exchange local time decides which
day a session belongs to; Adam's display timezone never affects trading hours (§1.7).
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from enum import StrEnum
from functools import cache
from zoneinfo import ZoneInfo

import exchange_calendars as xcals
import pandas as pd

from jarvis.risk.engine import MarketSession


class Exchange(StrEnum):
    """ISO 10383 MIC codes, as used by ``exchange_calendars``."""

    NYSE = "XNYS"
    STOCKHOLM = "XSTO"
    HELSINKI = "XHEL"
    COPENHAGEN = "XCSE"
    OSLO = "XOSL"


class CalendarRangeError(Exception):
    """The date is outside the published calendar. Jarvis must not guess trading hours."""


@cache
def _calendar(exchange: Exchange) -> xcals.ExchangeCalendar:
    return xcals.get_calendar(exchange.value)


def _utc(timestamp: pd.Timestamp) -> datetime:
    moment: datetime = timestamp.to_pydatetime()
    return moment.astimezone(UTC)


def exchange_timezone(exchange: Exchange) -> ZoneInfo:
    return ZoneInfo(str(_calendar(exchange).tz))


def session_on(exchange: Exchange, day: date) -> MarketSession:
    """The regular session on ``day`` (exchange-local date); closed days have no times."""
    calendar = _calendar(exchange)
    label = pd.Timestamp(day)
    if not calendar.first_session <= label <= calendar.last_session:
        raise CalendarRangeError(f"{exchange.value} calendar does not cover {day.isoformat()}")
    if not calendar.is_session(label):
        return MarketSession(None, None)
    return MarketSession(_utc(calendar.session_open(label)), _utc(calendar.session_close(label)))


def session_at(exchange: Exchange, now: datetime) -> MarketSession:
    """The session for the exchange-local date of ``now``."""
    if now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    return session_on(exchange, now.astimezone(exchange_timezone(exchange)).date())


def next_open(exchange: Exchange, after: datetime) -> datetime:
    """The first session open strictly after ``after``."""
    if after.utcoffset() is None:
        raise ValueError("after must be timezone-aware")
    calendar = _calendar(exchange)
    moment = pd.Timestamp(after.astimezone(UTC)).floor("min")
    if moment >= calendar.last_minute:
        raise CalendarRangeError(f"{exchange.value} calendar ends {calendar.last_session.date()}")
    return _utc(calendar.next_open(moment))
