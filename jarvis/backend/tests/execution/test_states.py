from __future__ import annotations

import pytest

from jarvis.broker.models import OrderStatus as S
from jarvis.execution.states import InvalidTransitionError, check_transition


@pytest.mark.parametrize(
    ("current", "new"),
    [
        (S.NEW, S.SUBMITTED),
        (S.NEW, S.FILLED),
        (S.NEW, S.REJECTED),
        (S.SUBMITTED, S.PARTIALLY_FILLED),
        (S.SUBMITTED, S.EXPIRED),
        (S.PARTIALLY_FILLED, S.FILLED),
        (S.PARTIALLY_FILLED, S.CANCELLED),
        (S.FILLED, S.FILLED),
    ],
)
def test_allowed(current: S, new: S) -> None:
    check_transition(current, new, filled_before=0, filled_after=0)


@pytest.mark.parametrize(
    ("current", "new", "match"),
    [
        (S.FILLED, S.SUBMITTED, "final"),
        (S.CANCELLED, S.FILLED, "final"),
        (S.PARTIALLY_FILLED, S.SUBMITTED, "go back"),
        (S.SUBMITTED, S.NEW, "go back"),
    ],
)
def test_forbidden(current: S, new: S, match: str) -> None:
    with pytest.raises(InvalidTransitionError, match=match):
        check_transition(current, new, filled_before=0, filled_after=0)


def test_filled_quantity_never_shrinks() -> None:
    with pytest.raises(InvalidTransitionError, match="went down"):
        check_transition(S.PARTIALLY_FILLED, S.PARTIALLY_FILLED, filled_before=5, filled_after=4)
