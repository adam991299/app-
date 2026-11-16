from __future__ import annotations

from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from jarvis.config.settings import CircuitBreakers
from jarvis.risk.breakers import Controls, EquityMarks, SystemHealth, TradingState, evaluate
from jarvis.risk.reasons import Reason

LIMITS = CircuitBreakers()
HEALTHY = SystemHealth(True, 0, 0.0, positions_reconciled=True)
FREE = Controls(paused=False, kill_switch_engaged=False)


def marks(
    current: str,
    *,
    day: str = "100",
    week: str = "100",
    peak: str = "100",
    day_low: str | None = None,
    week_low: str | None = None,
) -> EquityMarks:
    low = min(Decimal(current), Decimal(day))
    d_low = Decimal(day_low) if day_low is not None else low
    w_low = Decimal(week_low) if week_low is not None else min(d_low, Decimal(week))
    return EquityMarks(Decimal(day), d_low, Decimal(week), w_low, Decimal(peak), Decimal(current))


def test_healthy_system_is_active() -> None:
    status = evaluate(marks("100"), HEALTHY, FREE, LIMITS)
    assert status.state is TradingState.ACTIVE
    assert status.reasons == ()
    assert not status.kill_switch_should_engage
    assert status.state.allows_new_positions
    assert status.state.allows_closing


@pytest.mark.parametrize(
    ("current", "expected"),
    [
        ("98.01", TradingState.ACTIVE),  # 1.99 % daily loss
        ("98", TradingState.NO_NEW_TRADES),  # exactly 2 %
        ("96", TradingState.CLOSING_ONLY),  # 4 % weekly (also daily)
        ("90", TradingState.KILL_SWITCH),  # 10 % from peak
    ],
)
def test_loss_levels(current: str, expected: TradingState) -> None:
    assert evaluate(marks(current), HEALTHY, FREE, LIMITS).state is expected


def test_weekly_limit_counts_from_week_start() -> None:
    status = evaluate(marks("96.9", day="97.5", week="101", peak="101"), HEALTHY, FREE, LIMITS)
    assert status.state is TradingState.CLOSING_ONLY
    assert status.reasons == (Reason.WEEKLY_LOSS_LIMIT,)


def test_drawdown_engages_kill_switch_once() -> None:
    first = evaluate(marks("89", peak="100", day="89.5", week="89.5"), HEALTHY, FREE, LIMITS)
    assert first.state is TradingState.KILL_SWITCH
    assert first.kill_switch_should_engage
    assert first.reasons == (Reason.KILL_SWITCH_DRAWDOWN,)
    latched = Controls(paused=False, kill_switch_engaged=True)
    second = evaluate(marks("89", peak="100", day="89.5", week="89.5"), HEALTHY, latched, LIMITS)
    assert second.state is TradingState.KILL_SWITCH
    assert not second.kill_switch_should_engage


def test_engaged_kill_switch_stays_on_after_recovery() -> None:
    latched = Controls(paused=False, kill_switch_engaged=True)
    status = evaluate(marks("100"), HEALTHY, latched, LIMITS)
    assert status.state is TradingState.KILL_SWITCH
    assert status.reasons == (Reason.KILL_SWITCH_ENGAGED,)
    assert status.state.allows_closing
    assert not status.state.allows_new_positions


def test_pause() -> None:
    status = evaluate(
        marks("100"), HEALTHY, Controls(paused=True, kill_switch_engaged=False), LIMITS
    )
    assert status.state is TradingState.PAUSED
    assert status.reasons == (Reason.PAUSED,)


@pytest.mark.parametrize(
    ("health", "reason"),
    [
        (SystemHealth(False, 0, 0.0, True), Reason.BROKER_DISCONNECTED),
        (SystemHealth(True, 5, 0.0, True), Reason.BROKER_ERRORS),
        (SystemHealth(True, 0, 1.01, True), Reason.CLOCK_DRIFT),
        (SystemHealth(True, 0, -1.5, True), Reason.CLOCK_DRIFT),
        (SystemHealth(True, 0, 0.0, False), Reason.NOT_RECONCILED),
        (
            SystemHealth(True, 0, 0.0, True, account_mode_matches=False),
            Reason.ACCOUNT_MODE_MISMATCH,
        ),
    ],
)
def test_unhealthy_system_halts_everything(health: SystemHealth, reason: Reason) -> None:
    status = evaluate(marks("100"), health, FREE, LIMITS)
    assert status.state is TradingState.HALTED
    assert status.reasons == (reason,)
    assert not status.state.allows_closing


def test_below_error_threshold_is_fine() -> None:
    assert evaluate(marks("100"), SystemHealth(True, 4, 1.0, True), FREE, LIMITS).state is (
        TradingState.ACTIVE
    )


def test_all_reasons_are_reported_most_severe_state_wins() -> None:
    status = evaluate(
        marks("89"),
        SystemHealth(False, 0, 0.0, True),
        Controls(paused=True, kill_switch_engaged=False),
        LIMITS,
    )
    assert status.state is TradingState.HALTED
    assert status.reasons == (
        Reason.BROKER_DISCONNECTED,
        Reason.KILL_SWITCH_DRAWDOWN,
        Reason.PAUSED,
        Reason.WEEKLY_LOSS_LIMIT,
        Reason.DAILY_LOSS_LIMIT,
    )
    assert status.kill_switch_should_engage


def test_daily_limit_holds_for_the_rest_of_the_day() -> None:
    recovered = marks("99", day_low="97.9")  # fell 2.1 %, then recovered to -1 %
    status = evaluate(recovered, HEALTHY, FREE, LIMITS)
    assert status.state is TradingState.NO_NEW_TRADES
    assert status.reasons == (Reason.DAILY_LOSS_LIMIT,)


def test_weekly_limit_holds_until_next_week() -> None:
    # Monday fell 4.1 %; today (new day) the account is up, but the week's low remains
    status = evaluate(
        marks("97", day="96.5", week="100", day_low="96.5", week_low="95.9"), HEALTHY, FREE, LIMITS
    )
    assert status.state is TradingState.CLOSING_ONLY
    assert status.reasons == (Reason.WEEKLY_LOSS_LIMIT,)


@pytest.mark.parametrize(
    ("day", "day_low", "week", "week_low", "peak", "current", "match"),
    [
        ("0", "0", "1", "0", "1", "1", "positive"),
        ("1", "1", "0", "0", "1", "1", "positive"),
        ("1", "0", "1", "0", "0", "0", "positive"),
        ("1", "1", "1", "1", "1", "2", "peak"),
        ("1", "1.5", "2", "1", "2", "1.5", "day_low"),
        ("2", "1", "2", "1.5", "2", "1.5", "week_low"),
    ],
)
def test_equity_marks_validation(
    day: str, day_low: str, week: str, week_low: str, peak: str, current: str, match: str
) -> None:
    with pytest.raises(ValueError, match=match):
        EquityMarks(
            Decimal(day),
            Decimal(day_low),
            Decimal(week),
            Decimal(week_low),
            Decimal(peak),
            Decimal(current),
        )


@given(
    peak=st.decimals(min_value=1, max_value=10**9, places=2),
    drop=st.decimals(min_value=0, max_value=1, places=4),
)
def test_no_new_positions_whenever_any_loss_limit_is_hit(peak: Decimal, drop: Decimal) -> None:
    current = peak * (1 - drop)
    if current <= 0:
        return
    status = evaluate(
        EquityMarks(peak, current, peak, current, peak, current), HEALTHY, FREE, LIMITS
    )
    if drop >= Decimal("0.02"):
        assert not status.state.allows_new_positions
    else:
        assert status.state is TradingState.ACTIVE
