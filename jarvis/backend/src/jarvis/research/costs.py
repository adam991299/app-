"""Cost model for backtests (spec §6.3 item 1). Every number here is an assumption until
checked against IBKR's price list and real fills (see ASSUMPTIONS A21); the learning loop
replaces them with measured values (§5.5, "varje affär").
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CostModel:
    commission_per_share: float = 0.005  # IBKR Pro Fixed, US stocks (A21)
    commission_min: float = 1.0
    commission_max_pct: float = 1.0  # of trade value
    half_spread_bps: float = 2.0  # large US caps
    impact_bps_at_1pct_adv: float = 10.0  # market impact grows with sqrt(participation)
    fx_bps: float = 2.0  # SEK<->USD conversion, each way

    def commission(self, shares: float, price: float) -> float:
        if shares <= 0:
            return 0.0
        raw = max(shares * self.commission_per_share, self.commission_min)
        return min(raw, shares * price * self.commission_max_pct / 100)

    def slippage_per_share(self, price: float, shares: float, adv_shares: float) -> float:
        """Half the spread plus impact that grows with the square root of size vs volume."""
        participation = shares / adv_shares if adv_shares > 0 else 1.0
        impact = self.impact_bps_at_1pct_adv * math.sqrt(participation / 0.01)
        return price * (self.half_spread_bps + impact) / 10_000

    def total(self, shares: float, price: float, adv_shares: float) -> float:
        """All costs of one fill, in the instrument's currency."""
        if shares <= 0:
            return 0.0
        value = shares * price
        return (
            self.commission(shares, price)
            + shares * self.slippage_per_share(price, shares, adv_shares)
            + value * self.fx_bps / 10_000
        )
