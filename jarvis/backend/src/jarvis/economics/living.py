""" "Kan jag leva på det?" (§1.5): Monte Carlo of a portfolio paying a monthly living cost.

Returns are uneven on purpose: each simulated year draws its return from a fat-tailed
distribution, so losing years, drawdowns and the sequence-of-returns risk of withdrawing
during a fall are all in it. A buffer of living costs (at least 12 months) is never traded,
and withdrawals are cut while the portfolio is in a drawdown (the withdrawal rule).
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Plan:
    capital: float  # kr, including the buffer
    monthly_need: float  # kr
    expected_return_pct: float  # per year, after costs and tax
    volatility_pct: float  # per year
    years: int = 30
    buffer_months: int = 12
    drawdown_cut_pct: float = 30.0  # withdrawals cut by this much in a drawdown over 10 %


@dataclass(frozen=True, slots=True)
class Outcome:
    survival_pct: float  # simulations that never ran out of money
    median_end: float
    worst_tenth_end: float  # 10th percentile of the final capital
    worst_drawdown_median_pct: float


def _yearly_return(rng: random.Random, mean: float, vol: float) -> float:
    """Student-t with 4 degrees of freedom, scaled to the given volatility: fat tails."""
    t = rng.gauss(0, 1) / math.sqrt(sum(rng.gauss(0, 1) ** 2 for _ in range(4)) / 4)
    return mean + vol * t / math.sqrt(2)  # t(4) has variance 2


def simulate(plan: Plan, runs: int = 2000, seed: int = 1) -> Outcome:
    if plan.capital <= 0 or plan.monthly_need < 0 or plan.buffer_months < 12:
        raise ValueError("capital must be positive and the buffer at least 12 months")
    rng = random.Random(seed)  # noqa: S311 - reproducible planning, not security
    mean, vol = plan.expected_return_pct / 100, plan.volatility_pct / 100
    ends, drawdowns, survived = [], [], 0
    for _ in range(runs):
        buffer = min(plan.capital, plan.monthly_need * plan.buffer_months)
        invested = plan.capital - buffer
        peak, worst, alive = invested, 0.0, True
        for _year in range(plan.years):
            yearly = max(_yearly_return(rng, mean, vol), -0.99)  # a year can lose almost all
            monthly = (1 + yearly) ** (1 / 12) - 1
            for _month in range(12):
                invested *= 1 + monthly
                peak = max(peak, invested)
                drawdown = (peak - invested) / peak if peak > 0 else 0.0
                worst = max(worst, drawdown)
                need = plan.monthly_need
                if drawdown > 0.10:
                    need *= 1 - plan.drawdown_cut_pct / 100
                take = min(need, invested)
                invested -= take
                buffer -= need - take  # the buffer covers what the portfolio could not
                if buffer < 0:
                    alive = False
                    buffer = 0.0
                    break
            if not alive:
                break
        survived += alive
        ends.append(invested + buffer if alive else 0.0)
        drawdowns.append(worst * 100)
    ends.sort()
    drawdowns.sort()
    return Outcome(
        survival_pct=survived / runs * 100,
        median_end=ends[runs // 2],
        worst_tenth_end=ends[runs // 10],
        worst_drawdown_median_pct=drawdowns[runs // 2],
    )


def capital_needed(monthly_need: float, real_return_pct: float) -> float:
    """The simple rule of thumb, before any Monte Carlo: capital whose return alone pays the
    yearly need. Not defined for a return of zero or less."""
    if real_return_pct <= 0:
        raise ValueError("needs a positive return")
    return monthly_need * 12 / (real_return_pct / 100)


@dataclass(frozen=True, slots=True)
class Growth:
    deposited: float  # start + all monthly deposits
    low: float  # 10th percentile of the final value
    median: float
    high: float  # 90th percentile
    below_deposits_pct: float  # simulations that end below what was put in


def grow(
    start: float,
    monthly_deposit: float,
    years: int,
    expected_return_pct: float,
    volatility_pct: float,
    runs: int = 2000,
    seed: int = 1,
) -> Growth:
    """Small capital with regular deposits: the range of outcomes, losing years included."""
    if start < 0 or monthly_deposit < 0 or years < 1:
        raise ValueError("amounts cannot be negative and the horizon is at least a year")
    rng = random.Random(seed)  # noqa: S311 - reproducible planning, not security
    mean, vol = expected_return_pct / 100, volatility_pct / 100
    deposited = start + monthly_deposit * 12 * years
    ends = []
    for _ in range(runs):
        value = start
        for _year in range(years):
            yearly = max(_yearly_return(rng, mean, vol), -0.99)
            monthly = (1 + yearly) ** (1 / 12) - 1
            for _month in range(12):
                value = value * (1 + monthly) + monthly_deposit
        ends.append(value)
    ends.sort()
    below = sum(end < deposited for end in ends) / runs * 100
    return Growth(deposited, ends[runs // 10], ends[runs // 2], ends[runs * 9 // 10], below)
