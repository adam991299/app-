"""Backtest of the opening range breakout on 5-minute bars (spec §6.2.1).

Same rules as live: entry at the open after a breakout bar, stop at the range low, target at
``target_r`` times the risk, everything closed at the bar that starts ``flat_minutes`` before the
close. When stop and target are both inside one bar, the stop is assumed first (the worse
case). After three losing trades in a row the strategy sits out the next day.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from itertools import groupby
from statistics import fmean

from jarvis.research.costs import CostModel
from jarvis.research.event_backtest import BacktestResult, Trade, size
from jarvis.research.metrics import returns
from jarvis.research.validation import Evaluation
from jarvis.strategy.orb import BAR, IntradayBar, OrbParameters

PAUSE_AFTER_LOSSES = 3


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
    cash, losses_in_row, sit_out, index = capital, 0, False, 0

    def close_out(position: _Open, price: float, at_index: int) -> float:
        nonlocal losses_in_row
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
        losses_in_row = losses_in_row + 1 if trade.pnl < 0 else 0
        return position.shares * price - exit_cost

    for day, group in groupby(bars, key=lambda b: b.day):
        session = list(group)
        close = session[-1].at + BAR
        flat = close - timedelta(minutes=params.flat_minutes)
        last_entry_end = close - timedelta(minutes=params.last_entry_minutes)
        opening = session[: params.range_bars]
        high = float(max(b.high for b in opening))
        low = float(min(b.low for b in opening))
        held: _Open | None = None
        pending, traded, sit_out = False, sit_out, False

        for offset, bar in enumerate(session):
            i = index + offset
            o, h, lo, c = float(bar.open), float(bar.high), float(bar.low), float(bar.close)
            if held is not None:
                if bar.at >= flat:
                    cash += close_out(held, o, i)
                    held = None
                elif lo <= held.stop:
                    cash += close_out(held, min(o, held.stop), i)
                    held = None
                elif h >= held.target:
                    cash += close_out(held, max(o, held.target), i)
                    held = None
            if pending and held is None and bar.at < flat:
                pending = False
                wanted = size(cash, o, low, risk_pct, max_position_pct)
                if wanted and o > low:
                    cost = model.total(wanted, o, adv_shares)
                    cash -= wanted * o + cost
                    target = o + float(params.target_r) * (o - low)
                    held = _Open(wanted, o, low, target, i, cost)
                    if lo <= low:
                        cash += close_out(held, low, i)
                        held = None
            if (
                not traded
                and held is None
                and offset >= params.range_bars
                and bar.at + BAR <= last_entry_end
                and c > high
            ):
                pending, traded = True, True
        if losses_in_row >= PAUSE_AFTER_LOSSES:
            sit_out, losses_in_row = True, 0
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
