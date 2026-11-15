"""Event-driven backtest of the trend strategy, bar by bar, using the very functions the
live system uses (``strategy.trend``). Rules (the same as live):

- The setup is judged on a closed bar; the entry is at the next bar's open.
- The initial stop is set at signal time; if the next open is already at or below it, no
  entry.
- Size: the largest share count with risk to the stop ≤ ``risk_pct`` of equity and position
  value ≤ ``max_position_pct`` of equity (the risk engine's limits).
- During a bar the stop is checked first: an open at or below the stop exits at the open
  (a gap), otherwise a low at or below the stop exits at the stop.
- After each close the stop is raised to the trailing level, never lowered.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from jarvis.research.costs import CostModel
from jarvis.strategy.bars import Bar
from jarvis.strategy.trend import TrendParameters, entry_setup, trailing_stop


@dataclass(frozen=True, slots=True)
class Trade:
    entry_index: int
    exit_index: int
    shares: int
    entry_price: float
    exit_price: float
    costs: float

    @property
    def pnl(self) -> float:
        return (self.exit_price - self.entry_price) * self.shares - self.costs


@dataclass(slots=True)
class BacktestResult:
    equity: list[float] = field(default_factory=list)  # at each close
    trades: list[Trade] = field(default_factory=list)


def size(equity: float, entry: float, stop: float, risk_pct: float, max_position_pct: float) -> int:
    if entry <= stop or entry <= 0:
        return 0
    by_risk = equity * risk_pct / 100 / (entry - stop)
    by_value = equity * max_position_pct / 100 / entry
    return max(math.floor(min(by_risk, by_value)), 0)


def run_event(
    bars: list[Bar],
    params: TrendParameters,
    *,
    capital: float = 100_000.0,
    costs: CostModel | None = None,
    risk_pct: float = 0.75,
    max_position_pct: float = 10.0,
    adv_shares: float = 1e9,
) -> BacktestResult:
    model = costs or CostModel()
    result = BacktestResult()
    cash = capital
    shares = 0
    entry_price = stop = 0.0
    entry_index = 0
    entry_cost = 0.0
    pending_stop: float | None = None

    for i, bar in enumerate(bars):
        opened, low, close = float(bar.open), float(bar.low), float(bar.close)
        # 1. a position may be stopped out during the bar
        if shares and low <= stop:
            exit_price = opened if opened <= stop else stop
            exit_cost = model.total(shares, exit_price, adv_shares)
            cash += shares * exit_price - exit_cost
            result.trades.append(
                Trade(entry_index, i, shares, entry_price, exit_price, entry_cost + exit_cost)
            )
            shares = 0
        # 2. a signal from the previous close is entered at this open
        if pending_stop is not None and not shares:
            equity = cash
            wanted = size(equity, opened, pending_stop, risk_pct, max_position_pct)
            if wanted and opened > pending_stop:
                entry_cost = model.total(wanted, opened, adv_shares)
                cash -= wanted * opened + entry_cost
                shares, entry_price, stop, entry_index = wanted, opened, pending_stop, i
                if low <= stop:  # stopped out on the entry bar itself
                    exit_price = stop
                    exit_cost = model.total(shares, exit_price, adv_shares)
                    cash += shares * exit_price - exit_cost
                    result.trades.append(
                        Trade(i, i, shares, entry_price, exit_price, entry_cost + exit_cost)
                    )
                    shares = 0
        pending_stop = None
        # 3. after the close: raise the stop, or look for a new setup
        history = bars[: i + 1]
        if shares:
            trail = trailing_stop(history, params)
            if trail is not None:
                stop = max(stop, float(trail))
        else:
            setup = entry_setup(history, params)
            if setup is not None:
                pending_stop = float(setup.stop_price)
        result.equity.append(cash + shares * close)
    return result
