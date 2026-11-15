from __future__ import annotations

from datetime import UTC, datetime

import pytest

from jarvis.store.periods import day_start, week_start


def test_day_starts_at_midnight_in_stockholm() -> None:
    # 23:30 UTC on Monday is already Tuesday 00:30 in Stockholm (winter, UTC+1)
    assert day_start(datetime(2026, 11, 16, 23, 30, tzinfo=UTC)) == datetime(
        2026, 11, 16, 23, tzinfo=UTC
    )
    # summer time, UTC+2
    assert day_start(datetime(2026, 6, 16, 12, tzinfo=UTC)) == datetime(2026, 6, 15, 22, tzinfo=UTC)


def test_week_starts_monday_midnight_in_stockholm() -> None:
    sunday_evening = datetime(2026, 11, 22, 20, tzinfo=UTC)
    assert week_start(sunday_evening) == datetime(2026, 11, 15, 23, tzinfo=UTC)
    monday_early = datetime(2026, 11, 22, 23, 30, tzinfo=UTC)  # Monday 00:30 local
    assert week_start(monday_early) == datetime(2026, 11, 22, 23, tzinfo=UTC)


def test_week_spanning_the_daylight_saving_change() -> None:
    # Sweden leaves summer time on Sunday 25 Oct 2026; that week began Monday 19 Oct (UTC+2)
    assert week_start(datetime(2026, 10, 25, 12, tzinfo=UTC)) == datetime(
        2026, 10, 18, 22, tzinfo=UTC
    )


@pytest.mark.parametrize("call", [day_start, week_start])
def test_naive_is_rejected(call: object) -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        call(datetime(2026, 1, 1))  # type: ignore[operator]  # noqa: DTZ001
