"""Choosing between entry signals by what they are expected to earn (D31).

Every signal carries its expected result (validated edge times the risk) and its round-trip
costs, both in the base currency. A signal is worth sending only when the result is at least
``min_edge_to_cost_ratio`` times the costs; the risk engine enforces the same rule, this
module only avoids sending what it would refuse. When signals compete for cash or open
slots, the one with the largest expected result after costs goes first.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from jarvis.config.settings import Risk
from jarvis.execution.engine import EntrySignal


def net_edge(signal: EntrySignal) -> Decimal:
    """Expected result after costs, in the base currency."""
    return signal.expected_edge - signal.estimated_cost


def worth_it(signal: EntrySignal, risk: Risk) -> bool:
    ratio = Decimal(str(risk.turnover.min_edge_to_cost_ratio))
    return signal.expected_edge > 0 and signal.expected_edge >= signal.estimated_cost * ratio


def best_first[T](items: Sequence[tuple[EntrySignal, T]]) -> list[tuple[EntrySignal, T]]:
    return sorted(items, key=lambda item: net_edge(item[0]), reverse=True)
