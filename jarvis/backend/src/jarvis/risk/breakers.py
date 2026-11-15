"""Circuit breakers, kill switch and system-health stops (spec §7, §11).

``evaluate`` is pure: it reads equity marks, system health and Adam's controls and
returns the trading state. Latching the kill switch (and requiring Adam to restart) is
the caller's job: when ``kill_switch_should_engage`` is true the caller must persist
``Controls.kill_switch_engaged = True``. Resetting it re-bases the equity peak, so the
same drawdown does not trip it again immediately.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from jarvis.config.settings import CircuitBreakers
from jarvis.risk.reasons import Reason
from jarvis.risk.units import fraction


class TradingState(StrEnum):
    """Ordered from most to least restrictive."""

    HALTED = "halted"  # system unhealthy: no orders at all
    KILL_SWITCH = "kill_switch"  # no new positions until Adam restarts; closing allowed
    PAUSED = "paused"  # Adam paused; closing allowed
    CLOSING_ONLY = "closing_only"  # weekly loss limit; closing allowed
    NO_NEW_TRADES = "no_new_trades"  # daily loss limit; closing allowed
    ACTIVE = "active"

    @property
    def allows_new_positions(self) -> bool:
        return self is TradingState.ACTIVE

    @property
    def allows_closing(self) -> bool:
        return self is not TradingState.HALTED


@dataclass(frozen=True, slots=True)
class EquityMarks:
    """Net liquidation value at the reference points, in base currency."""

    day_start: Decimal
    week_start: Decimal
    peak: Decimal
    current: Decimal

    def __post_init__(self) -> None:
        if min(self.day_start, self.week_start, self.peak) <= 0:
            raise ValueError("reference equity values must be positive")
        if self.current > self.peak:
            raise ValueError("current equity cannot exceed the recorded peak")


@dataclass(frozen=True, slots=True)
class SystemHealth:
    broker_connected: bool
    consecutive_broker_errors: int
    clock_drift_seconds: float
    positions_reconciled: bool


@dataclass(frozen=True, slots=True)
class Controls:
    """Adam's persistent switches."""

    paused: bool
    kill_switch_engaged: bool


@dataclass(frozen=True, slots=True)
class BreakerStatus:
    state: TradingState
    reasons: tuple[Reason, ...]
    kill_switch_should_engage: bool


def _loss_fraction(reference: Decimal, current: Decimal) -> Decimal:
    return (reference - current) / reference


def evaluate(
    marks: EquityMarks, health: SystemHealth, controls: Controls, limits: CircuitBreakers
) -> BreakerStatus:
    halted: list[Reason] = []
    if not health.broker_connected:
        halted.append(Reason.BROKER_DISCONNECTED)
    if health.consecutive_broker_errors >= limits.max_consecutive_broker_errors:
        halted.append(Reason.BROKER_ERRORS)
    if abs(health.clock_drift_seconds) > limits.max_clock_drift_seconds:
        halted.append(Reason.CLOCK_DRIFT)
    if not health.positions_reconciled:
        halted.append(Reason.NOT_RECONCILED)

    drawdown_hit = _loss_fraction(marks.peak, marks.current) >= fraction(
        limits.kill_switch_drawdown_pct
    )
    kill: list[Reason] = []
    if controls.kill_switch_engaged:
        kill.append(Reason.KILL_SWITCH_ENGAGED)
    if drawdown_hit:
        kill.append(Reason.KILL_SWITCH_DRAWDOWN)

    weekly = _loss_fraction(marks.week_start, marks.current) >= fraction(limits.weekly_loss_pct)
    daily = _loss_fraction(marks.day_start, marks.current) >= fraction(limits.daily_loss_pct)

    layers: list[tuple[TradingState, list[Reason]]] = [
        (TradingState.HALTED, halted),
        (TradingState.KILL_SWITCH, kill),
        (TradingState.PAUSED, [Reason.PAUSED] if controls.paused else []),
        (TradingState.CLOSING_ONLY, [Reason.WEEKLY_LOSS_LIMIT] if weekly else []),
        (TradingState.NO_NEW_TRADES, [Reason.DAILY_LOSS_LIMIT] if daily else []),
    ]
    state = next((s for s, reasons in layers if reasons), TradingState.ACTIVE)
    reasons = tuple(reason for _, layer in layers for reason in layer)
    return BreakerStatus(
        state=state,
        reasons=reasons,
        kill_switch_should_engage=drawdown_hit and not controls.kill_switch_engaged,
    )
