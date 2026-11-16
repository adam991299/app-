"""Backtest of the opening range breakout on 5-minute bars (spec §6.2.1).

Same rules as live: entry at the open after a breakout bar, stop at the range low, target at
``target_r`` times the risk, everything closed at the bar that starts ``flat_minutes`` before the
close. When stop and target are both inside one bar, the stop is assumed first (the worse
case). Up to ``MAX_TRADES_PER_SYMBOL`` trades a day, a new one only after a bar that starts
after the previous exit closes above the day's high so far (``setup_for``).

Each symbol is tested on its own, so the account-wide limits of live trading (open day
trades at once, the daily loss limit, the pause after losses in a row) are not modelled;
they can only make live trading more cautious than the backtest.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from itertools import groupby
from statistics import fmean

from jarvis.research.costs import CostModel
from jarvis.research.event_backtest import BacktestResult, Trade, size
from jarvis.research.metrics import returns
from jarvis.research.validation import Evaluation
from jarvis.strategy.orb import (
    BAR,
    MAX_TRADES_PER_SYMBOL,
    IntradayBar,
    OrbParameters,
)


@dataclass(slots=True)
class _Open:
    shares: int
    entry: float
    stop: float
    target: float
    index: int
    cost: float


def run_orb(
    bars: list[IntradayBar],
    params: OrbParameters,
    *,
    capital: float = 100_000.0,
    costs: CostModel | None = None,
    risk_pct: float = 0.75,
    max_position_pct: float = 10.0,
    adv_shares: float = 1e9,
) -> tuple[BacktestResult, list[date]]:
    """Returns the result (equity at each day's close) and the day of each equity point."""
    model = costs or CostModel()
    result, days = BacktestResult(), []
    cash, index = capital, 0

    def close_out(position: _Open, price: float, at_index: int) -> float:
        exit_cost = model.total(position.shares, price, adv_shares)
        trade = Trade(
            position.index,
            at_index,
            position.shares,
            position.entry,
            price,
            position.cost + exit_cost,
            position.stop,
        )
        result.trades.append(trade)
        return position.shares * price - exit_cost

    for day, group in groupby(bars, key=lambda b: b.day):
        session = list(group)
        close = session[-1].at + BAR
        flat = close - timedelta(minutes=params.flat_minutes)
        last_entry_end = close - timedelta(minutes=params.last_entry_minutes)
        opening = session[: params.range_bars]
        range_high = float(max(b.high for b in opening))
        low = float(min(b.low for b in opening))
        day_high = 0.0  # highest price of the bars before the current one
        held: _Open | None = None
        pending, taken = False, 0
        last_exit: datetime | None = None  # start of the bar in which the last trade ended

        def end(position: _Open, price: float, i: int, at: datetime) -> None:
            nonlocal cash, held, last_exit
            cash += close_out(position, price, i)
            held, last_exit = None, at

        for offset, bar in enumerate(session):
            i = index + offset
            o, h, lo, c = float(bar.open), float(bar.high), float(bar.low), float(bar.close)
            if held is not None:
                if bar.at >= flat:
                    end(held, o, i, bar.at)
                elif lo <= held.stop:
                    end(held, min(o, held.stop), i, bar.at)
                elif h >= held.target:
                    end(held, max(o, held.target), i, bar.at)
            if pending and held is None and bar.at < flat:
                pending = False
                wanted = size(cash, o, low, risk_pct, max_position_pct)
                if wanted and o > low:
                    taken += 1
                    cost = model.total(wanted, o, adv_shares)
                    cash -= wanted * o + cost
                    target = o + float(params.target_r) * (o - low)
                    held = _Open(wanted, o, low, target, i, cost)
                    if lo <= low:
                        end(held, low, i, bar.at)
            # The same rule as setup_for, kept incremental for speed (a test compares them).
            if (
                held is None
                and taken < MAX_TRADES_PER_SYMBOL
                and offset >= params.range_bars
                and bar.at + BAR <= last_entry_end
            ):
                if taken == 0:
                    pending = c > range_high
                else:
                    pending = last_exit is not None and bar.at > last_exit and c > day_high
            day_high = max(day_high, h)
        index += len(session)
        result.equity.append(cash)
        days.append(day)
    return result, days


def evaluate_orb(
    series: Mapping[str, list[IntradayBar]],
    params: OrbParameters,
    start: date,
    end: date,
    costs: CostModel,
) -> Evaluation:
    """Equal-weight portfolio of one ORB backtest per symbol, days in [start, end]."""
    per_day: dict[date, list[float]] = {}
    trades: list[Trade] = []
    for bars in series.values():
        window = [b for b in bars if start <= b.day <= end]
        if not window:
            continue
        capital = 100_000.0
        result, days = run_orb(window, params, capital=capital, costs=costs)
        for day, value in zip(days, returns([capital, *result.equity]), strict=True):
            per_day.setdefault(day, []).append(value)
        trades.extend(result.trades)
    return Evaluation({d: fmean(v) for d, v in per_day.items()}, trades)
