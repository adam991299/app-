from __future__ import annotations

import pytest

from jarvis.config.settings import Risk
from jarvis.risk.profiles import NAMES_SV, RiskProfile, apply_profile
from jarvis.store.profile import parse

BASE = Risk()


def test_balanced_is_the_spec_default() -> None:
    assert apply_profile(BASE, RiskProfile.BALANCED) == BASE


def test_offensive_takes_more_risk_inside_the_caps() -> None:
    risk = apply_profile(BASE, RiskProfile.OFFENSIVE)
    assert risk.per_trade.max_risk_pct == 1.5
    assert risk.portfolio.max_position_pct == 20
    assert risk.gap.max_gap_loss_pct == 5
    assert risk.circuit_breakers == BASE.circuit_breakers  # stops are never loosened
    assert risk.portfolio.max_position_pct <= risk.technical_max.single_stock_pct_of_budget


def test_cautious_takes_less() -> None:
    risk = apply_profile(BASE, RiskProfile.CAUTIOUS)
    assert (risk.per_trade.max_risk_pct, risk.portfolio.max_position_pct) == (0.5, 7.5)


def test_levels_are_ordered_and_named_in_swedish() -> None:
    assert [p.rank for p in RiskProfile] == [0, 1, 2]
    assert NAMES_SV[RiskProfile.OFFENSIVE] == "Offensiv"


def test_command_parsing() -> None:
    assert parse(["Offensiv"]) is RiskProfile.OFFENSIVE
    assert parse(["försiktig"]) is RiskProfile.CAUTIOUS
    with pytest.raises(ValueError, match="ange"):
        parse(["maxrisk"])
