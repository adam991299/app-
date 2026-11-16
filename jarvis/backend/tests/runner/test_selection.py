from __future__ import annotations

from decimal import Decimal

from jarvis.config.settings import Risk
from jarvis.execution.engine import EntrySignal
from jarvis.research.costs import CostModel
from jarvis.runner.selection import best_first, net_edge, worth_it
from tests.factories import instrument

D = Decimal


def signal(edge: str, cost: str, sid: str = "trend:AAPL:2026-11-16") -> EntrySignal:
    return EntrySignal(
        signal_id=sid,
        strategy="trend",
        instrument=instrument(),
        quantity=10,
        limit_price=D(100),
        stop_price=D(95),
        expected_edge=D(edge),
        estimated_cost=D(cost),
        explanation_sv="Test.",
    )


def test_a_signal_must_earn_twice_its_costs() -> None:
    risk = Risk()
    assert worth_it(signal("20", "10"), risk)
    assert not worth_it(signal("19.99", "10"), risk)
    assert not worth_it(signal("0", "0"), risk)
    assert net_edge(signal("20", "10")) == 10


def test_the_largest_result_after_costs_goes_first() -> None:
    small = signal("30", "10", "trend:A:2026-11-16")  # 20 after costs
    big = signal("100", "40", "trend:B:2026-11-16")  # 60 after costs
    middle = signal("50", "5", "trend:C:2026-11-16")  # 45 after costs
    ranked = best_first([(small, "a"), (big, "b"), (middle, "c")])
    assert [tag for _, tag in ranked] == ["b", "c", "a"]


def test_cost_model_follows_the_commission_plan() -> None:
    fixed, tiered = CostModel.for_plan("fixed"), CostModel.for_plan("tiered")
    assert fixed.commission(10, 100) == 1.0
    assert tiered.commission(10, 100) == 0.40
    assert tiered.commission(1000, 100) == 4.0
