"""Risk levels Adam chooses between (spec §9.2 "Risknivå", §7.1). Each is the balanced
default with a few limits moved, always inside the technical caps; the circuit breakers and
kill switch are the same in every level."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from jarvis.config.settings import Risk


class RiskProfile(StrEnum):
    CAUTIOUS = "cautious"
    BALANCED = "balanced"
    OFFENSIVE = "offensive"

    @property
    def rank(self) -> int:
        return list(RiskProfile).index(self)


NAMES_SV = {
    RiskProfile.CAUTIOUS: "Försiktig",
    RiskProfile.BALANCED: "Balanserad",
    RiskProfile.OFFENSIVE: "Offensiv",
}

# Per level: risk per trade (% of capital) and largest position (% of capital).
_LEVELS = {
    RiskProfile.CAUTIOUS: (0.5, 7.5),
    RiskProfile.OFFENSIVE: (1.5, 20.0),
}


def apply_profile(base: Risk, profile: RiskProfile) -> Risk:
    if profile is RiskProfile.BALANCED:
        return base
    risk_pct, position_pct = _LEVELS[profile]
    data: dict[str, Any] = base.model_dump()
    data["per_trade"]["max_risk_pct"] = min(risk_pct, base.circuit_breakers.daily_loss_pct)
    data["portfolio"]["max_position_pct"] = min(
        position_pct, base.technical_max.single_stock_pct_of_budget
    )
    if profile is RiskProfile.OFFENSIVE:
        # A 20 % position that gaps 25 % loses 5 % of the capital: the most this level allows.
        data["gap"]["max_gap_loss_pct"] = 5.0
    else:
        data["portfolio"]["max_position_small_cap_pct"] = min(
            base.portfolio.max_position_small_cap_pct, position_pct
        )
    return Risk.model_validate(data)
