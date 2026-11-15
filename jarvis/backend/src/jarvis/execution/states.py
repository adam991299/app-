"""The order state machine (§8): new → submitted → partially_filled → filled | cancelled |
rejected | expired. A terminal state never changes, and filled quantity never shrinks."""

from __future__ import annotations

from jarvis.broker.models import OrderStatus

_RANK = {
    OrderStatus.NEW: 0,
    OrderStatus.SUBMITTED: 1,
    OrderStatus.PARTIALLY_FILLED: 2,
}


class InvalidTransitionError(Exception):
    """The broker reported something impossible. Jarvis stops and alerts instead of guessing."""


def check_transition(
    current: OrderStatus, new: OrderStatus, *, filled_before: int, filled_after: int
) -> None:
    if filled_after < filled_before:
        raise InvalidTransitionError(f"filled quantity went down: {filled_before} → {filled_after}")
    if current is new:
        return
    if current.is_terminal:
        raise InvalidTransitionError(f"{current.value} is final, cannot become {new.value}")
    if not new.is_terminal and _RANK[new] < _RANK[current]:
        raise InvalidTransitionError(f"{current.value} cannot go back to {new.value}")
