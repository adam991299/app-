"""Vectorized backtest of the trend strategy: indicators come from pandas rolling windows,
written independently of ``strategy.trend``. It must agree with the event-driven backtest
(Fas 2 acceptance); a disagreement means a bug in one of them.

Stops depend on the path, so positions are walked in a short loop over precomputed arrays.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from jarvis.research.costs import CostModel
from jarvis.research.event_backtest import BacktestResult, Trade, size
from jarvis.strategy.bars import Bar
from jarvis.strategy.trend import TrendParameters


def indicators(frame: pd.DataFrame, params: TrendParameters) -> pd.DataFrame:
    high, low, close = frame["high"], frame["low"], frame["close"]
    previous_close = close.shift(1)
    true_range = pd.concat(
        [high - low, (high - previous_close).abs(), (low - previous_close).abs()], axis=1
    ).max(axis=1)
    true_range.iloc[0] = np.nan  # the first bar has no previous close
    out = pd.DataFrame(index=frame.index)
    out["channel_high"] = high.rolling(params.entry_lookback).max().shift(1)
    out["atr"] = true_range.rolling(params.atr_period).mean()
    out["trail"] = low.rolling(params.exit_lookback).min()
    enough = np.arange(len(frame)) >= params.bars_needed - 1
    stop = close - float(params.atr_stop_multiple) * out["atr"]
    out["signal"] = enough & (close > out["channel_high"]) & (out["atr"] > 0) & (stop > 0)
    out["signal_stop"] = stop
    return out


def signal_frame(bars: list[Bar], params: TrendParameters) -> pd.DataFrame:
    """Per bar: is there an entry signal at the close, and where would its stop be."""
    frame = pd.DataFrame(
        {
            "open": [float(b.open) for b in bars],
            "high": [float(b.high) for b in bars],
            "low": [float(b.low) for b in bars],
            "close": [float(b.close) for b in bars],
        }
    )
    return indicators(frame, params)


def run_vector(
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
    frame = pd.DataFrame(
        {
            "open": [float(b.open) for b in bars],
            "high": [float(b.high) for b in bars],
            "low": [float(b.low) for b in bars],
            "close": [float(b.close) for b in bars],
        }
    )
    ind = indicators(frame, params)
    opens, lows, closes = (frame[c].to_numpy() for c in ("open", "low", "close"))
    signal, signal_stop, trail = (
        ind["signal"].to_numpy(),
        ind["signal_stop"].to_numpy(),
        ind["trail"].to_numpy(),
    )

    result = BacktestResult()
    cash, shares, entry_price, stop, entry_index, entry_cost = capital, 0, 0.0, 0.0, 0, 0.0
    for i in range(len(frame)):
        if shares and lows[i] <= stop:
            exit_price = min(opens[i], stop)
            exit_cost = model.total(shares, exit_price, adv_shares)
            cash += shares * exit_price - exit_cost
            result.trades.append(
                Trade(entry_index, i, shares, entry_price, exit_price, entry_cost + exit_cost)
            )
            shares = 0
        if i > 0 and signal[i - 1] and not shares and opens[i] > signal_stop[i - 1]:
            wanted = size(cash, opens[i], signal_stop[i - 1], risk_pct, max_position_pct)
            if wanted:
                entry_cost = model.total(wanted, opens[i], adv_shares)
                cash -= wanted * opens[i] + entry_cost
                shares, entry_price, stop, entry_index = wanted, opens[i], signal_stop[i - 1], i
                if lows[i] <= stop:
                    exit_cost = model.total(shares, stop, adv_shares)
                    cash += shares * stop - exit_cost
                    result.trades.append(
                        Trade(i, i, shares, entry_price, stop, entry_cost + exit_cost)
                    )
                    shares = 0
        if shares and not np.isnan(trail[i]):
            stop = max(stop, trail[i])
        result.equity.append(cash + shares * closes[i])
    return result
