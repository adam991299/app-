"""Performance statistics, including the Deflated Sharpe Ratio (spec §6.3 item 5).

Bailey & López de Prado: the probabilistic Sharpe ratio asks how likely the true Sharpe
exceeds a benchmark given the sample's length, skew and fat tails; the deflated version
raises that benchmark to the best Sharpe expected by luck after ``trials`` attempts.
"""

from __future__ import annotations

import math
import random
from collections.abc import Sequence
from itertools import pairwise
from statistics import NormalDist, fmean, pstdev

from jarvis.research.event_backtest import Trade

EULER_GAMMA = 0.5772156649015329
NORMAL = NormalDist()
TRADING_DAYS = 252


def returns(equity: Sequence[float]) -> list[float]:
    return [b / a - 1 for a, b in pairwise(equity) if a > 0]


def sharpe(per_period: Sequence[float]) -> float:
    """Per-period Sharpe ratio (no risk-free rate: cash earns little in ISK)."""
    if len(per_period) < 2:
        return 0.0
    spread = pstdev(per_period)
    return fmean(per_period) / spread if spread > 0 else 0.0


def annualised_sharpe(per_day: Sequence[float]) -> float:
    return sharpe(per_day) * math.sqrt(TRADING_DAYS)


def max_drawdown(equity: Sequence[float]) -> float:
    """Largest fall from a peak, as a fraction (0.2 means -20 %)."""
    peak, worst = -math.inf, 0.0
    for value in equity:
        peak = max(peak, value)
        if peak > 0:
            worst = max(worst, (peak - value) / peak)
    return worst


def profit_factor(trades: Sequence[Trade]) -> float:
    gains = sum(t.pnl for t in trades if t.pnl > 0)
    losses = -sum(t.pnl for t in trades if t.pnl < 0)
    if losses == 0:
        return math.inf if gains > 0 else 0.0
    return gains / losses


def _moments(values: Sequence[float]) -> tuple[float, float]:
    """Skewness and (non-excess) kurtosis."""
    mean, spread = fmean(values), pstdev(values)
    if spread == 0:
        return 0.0, 3.0
    z = [(v - mean) / spread for v in values]
    return fmean(x**3 for x in z), fmean(x**4 for x in z)


def probabilistic_sharpe(per_period: Sequence[float], benchmark: float = 0.0) -> float:
    """Probability that the true per-period Sharpe exceeds ``benchmark``."""
    n = len(per_period)
    if n < 3:
        return 0.0
    estimate = sharpe(per_period)
    skew, kurt = _moments(per_period)
    # Never negative (kurtosis >= skew² + 1); exactly zero only for degenerate samples.
    variance = 1 - skew * estimate + (kurt - 1) / 4 * estimate**2
    if variance <= 0:
        return 0.0
    return NORMAL.cdf((estimate - benchmark) * math.sqrt(n - 1) / math.sqrt(variance))


def expected_max_sharpe(trial_sharpes: Sequence[float]) -> float:
    """The best per-period Sharpe one expects from luck alone after these trials."""
    trials = len(trial_sharpes)
    if trials < 2:
        return 0.0
    spread = pstdev(trial_sharpes)
    return spread * (
        (1 - EULER_GAMMA) * NORMAL.inv_cdf(1 - 1 / trials)
        + EULER_GAMMA * NORMAL.inv_cdf(1 - 1 / (trials * math.e))
    )


def deflated_sharpe(per_period: Sequence[float], trial_sharpes: Sequence[float]) -> float:
    return probabilistic_sharpe(per_period, expected_max_sharpe(trial_sharpes))


def drawdown_quantile(
    trades: Sequence[Trade], capital: float, quantile: float = 0.95, runs: int = 1000, seed: int = 7
) -> float:
    """Monte Carlo on the order of trades (§6.3 item 6): the drawdown that only
    ``1 - quantile`` of reshuffled histories exceed."""
    if not trades:
        return 0.0
    rng = random.Random(seed)  # noqa: S311 - reproducible research, not security
    pnls = [t.pnl for t in trades]
    worst = []
    for _ in range(runs):
        rng.shuffle(pnls)
        equity, curve = capital, [capital]
        for pnl in pnls:
            equity += pnl
            curve.append(equity)
        worst.append(max_drawdown(curve))
    worst.sort()
    return worst[min(int(quantile * runs), runs - 1)]
