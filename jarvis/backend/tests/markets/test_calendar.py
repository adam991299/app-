"""Time zones and daylight saving are tested explicitly (spec §11): Stockholm and New
York switch on different dates, which moves the US open in Swedish time for a few weeks."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from jarvis.markets.calendar import (
    CalendarRangeError,
    Exchange,
    exchange_timezone,
    next_open,
    session_at,
    session_on,
)

STHLM = ZoneInfo("Europe/Stockholm")


def utc(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=UTC)


def test_normal_nyse_day_in_winter() -> None:
    s = session_on(Exchange.NYSE, date(2026, 11, 16))
    assert (s.opens_at, s.closes_at) == (utc(2026, 11, 16, 14, 30), utc(2026, 11, 16, 21))
    assert s.opens_at is not None
    assert s.opens_at.astimezone(STHLM).hour == 15  # 15:30 in Stockholm


def test_holiday_and_half_day() -> None:
    thanksgiving = session_on(Exchange.NYSE, date(2026, 11, 26))
    assert thanksgiving.opens_at is None
    assert not thanksgiving.is_open(utc(2026, 11, 26, 16))
    black_friday = session_on(Exchange.NYSE, date(2026, 11, 27))
    assert black_friday.closes_at == utc(2026, 11, 27, 18)  # 13:00 New York


def test_weekend_is_closed() -> None:
    assert session_on(Exchange.STOCKHOLM, date(2026, 11, 14)).closes_at is None


def test_us_switches_to_summer_time_before_europe() -> None:
    before = session_on(Exchange.NYSE, date(2026, 3, 6))
    gap = session_on(Exchange.NYSE, date(2026, 3, 10))  # US on summer time, Sweden not yet
    after = session_on(Exchange.NYSE, date(2026, 3, 30))  # both on summer time
    assert before.opens_at is not None
    assert gap.opens_at is not None
    assert after.opens_at is not None
    assert before.opens_at.astimezone(STHLM).strftime("%H:%M") == "15:30"
    assert gap.opens_at.astimezone(STHLM).strftime("%H:%M") == "14:30"
    assert after.opens_at.astimezone(STHLM).strftime("%H:%M") == "15:30"


def test_stockholm_hours_follow_swedish_daylight_saving() -> None:
    winter = session_on(Exchange.STOCKHOLM, date(2026, 11, 16))
    summer = session_on(Exchange.STOCKHOLM, date(2026, 6, 16))
    assert winter.opens_at == utc(2026, 11, 16, 8)
    assert summer.opens_at == utc(2026, 6, 16, 7)
    assert winter.opens_at is not None
    assert summer.opens_at is not None
    assert winter.opens_at.astimezone(STHLM).hour == summer.opens_at.astimezone(STHLM).hour == 9


def test_session_at_uses_exchange_local_date() -> None:
    # 03:00 UTC Tuesday is still Monday evening in New York
    s = session_at(Exchange.NYSE, utc(2026, 11, 17, 3))
    assert s.opens_at == utc(2026, 11, 16, 14, 30)
    assert exchange_timezone(Exchange.NYSE) == ZoneInfo("America/New_York")


def test_next_open_skips_weekend_and_holiday() -> None:
    assert next_open(Exchange.NYSE, utc(2026, 11, 25, 22)) == utc(2026, 11, 27, 14, 30)
    assert next_open(Exchange.NYSE, utc(2026, 11, 14, 12)) == utc(2026, 11, 16, 14, 30)


def test_out_of_range_is_an_error_not_a_guess() -> None:
    far = date.today() + timedelta(days=800)  # noqa: DTZ011 - relative to the calendar's end
    with pytest.raises(CalendarRangeError):
        session_on(Exchange.NYSE, far)
    with pytest.raises(CalendarRangeError):
        next_open(Exchange.NYSE, datetime(far.year, far.month, far.day, tzinfo=UTC))


def test_naive_datetimes_are_rejected() -> None:
    naive = datetime(2026, 11, 16, 12)  # noqa: DTZ001
    with pytest.raises(ValueError, match="timezone-aware"):
        session_at(Exchange.NYSE, naive)
    with pytest.raises(ValueError, match="timezone-aware"):
        next_open(Exchange.NYSE, naive)


@pytest.mark.parametrize("exchange", list(Exchange))
def test_every_supported_exchange_has_a_calendar(exchange: Exchange) -> None:
    assert session_on(exchange, date(2026, 11, 16)).opens_at is not None
