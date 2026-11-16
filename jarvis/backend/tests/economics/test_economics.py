from __future__ import annotations

from decimal import Decimal

import pytest

from jarvis.config.settings import Tax
from jarvis.economics.costs import break_even
from jarvis.economics.isk import TaxFiguresMissingError, isk_tax, tax_drag_pct
from jarvis.economics.living import Plan, capital_needed, simulate

D = Decimal
# Example figures for the tests only; real ones are entered from Skatteverket each year.
FIGURES = Tax(tax_year=2026, isk_tax_free_level_sek=300000, isk_schablon_tax_pct=1.065)


def test_break_even_matches_the_specs_example() -> None:
    result = break_even({"data": D(1500), "server": D(500)}, D(100000), D(3))
    assert (result.monthly_costs, result.yearly_costs) == (D(2000), D(24000))
    assert result.required_return_pct == D(24)
    assert result.warning


def test_zero_costs_need_nothing() -> None:
    result = break_even({}, D(100000), D(3))
    assert result.required_return_pct == 0
    assert not result.warning


@pytest.mark.parametrize(("costs", "capital"), [({"x": D(-1)}, D(1)), ({}, D(0))])
def test_break_even_validation(costs: dict[str, Decimal], capital: Decimal) -> None:
    with pytest.raises(ValueError, match=r"negative|positive"):
        break_even(costs, capital, D(3))


def test_isk_tax_above_the_tax_free_level() -> None:
    result = isk_tax([D(400000), D(420000), D(380000), D(400000)], D(0), FIGURES)
    assert result.capital_base == D(400000)
    assert result.taxable_base == D(100000)
    assert result.tax == D(1065)


def test_deposits_count_and_small_accounts_pay_nothing() -> None:
    with_deposit = isk_tax([D(400000)] * 4, D(40000), FIGURES)
    assert with_deposit.capital_base == D(410000)
    assert isk_tax([D(100000)] * 4, D(0), FIGURES).tax == 0


def test_tax_is_never_guessed() -> None:
    with pytest.raises(TaxFiguresMissingError):
        isk_tax([D(1)] * 4, D(0), Tax())
    with pytest.raises(ValueError, match="not taxed as an ISK"):
        isk_tax([D(1)] * 4, D(0), Tax(model="capital_gains"))
    with pytest.raises(ValueError, match="four quarter"):
        isk_tax([D(1)] * 3, D(0), FIGURES)
    with pytest.raises(ValueError, match="negative"):
        isk_tax([D(1)] * 4, D(-1), FIGURES)


def test_tax_drag() -> None:
    assert tax_drag_pct(D(400000), FIGURES) == D(1065) / D(400000) * 100
    with pytest.raises(ValueError, match="positive"):
        tax_drag_pct(D(0), FIGURES)


def test_capital_needed() -> None:
    assert capital_needed(25000, 5) == pytest.approx(6_000_000)
    with pytest.raises(ValueError, match="positive return"):
        capital_needed(25000, 0)


def test_monte_carlo_shows_that_uneven_returns_matter() -> None:
    plan = Plan(capital=6_000_000, monthly_need=25_000, expected_return_pct=5, volatility_pct=15)
    calm = simulate(
        Plan(capital=6_000_000, monthly_need=25_000, expected_return_pct=5, volatility_pct=1),
        runs=300,
    )
    rough = simulate(plan, runs=300)
    assert calm.survival_pct >= rough.survival_pct
    assert rough.survival_pct < 100  # sequence risk: the "safe" 5 % rule is not safe
    assert rough.worst_tenth_end <= rough.median_end
    assert rough.worst_drawdown_median_pct > calm.worst_drawdown_median_pct


def test_too_little_capital_runs_out() -> None:
    poor = simulate(
        Plan(
            capital=400_000, monthly_need=25_000, expected_return_pct=5, volatility_pct=15, years=10
        ),
        runs=200,
    )
    assert poor.survival_pct == 0
    assert poor.median_end == 0


def test_plan_validation() -> None:
    with pytest.raises(ValueError, match="buffer"):
        simulate(
            Plan(
                capital=1, monthly_need=1, expected_return_pct=5, volatility_pct=1, buffer_months=6
            )
        )


def test_growth_with_monthly_deposits() -> None:
    from jarvis.economics.living import grow

    result = grow(80_000, 2_000, 5, expected_return_pct=8, volatility_pct=20, runs=500)
    assert result.deposited == 80_000 + 2_000 * 60
    assert result.low < result.median < result.high
    assert 0 < result.below_deposits_pct < 50  # losing overall is possible, not likely
    with pytest.raises(ValueError, match="negative"):
        grow(-1, 0, 1, 5, 10)
