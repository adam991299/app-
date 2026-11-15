from __future__ import annotations

from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from jarvis.config.settings import Risk
from jarvis.domain import AssetClass
from jarvis.risk.sizing import SizingLimit, gap_loss_per_unit, size_position
from tests.factories import instrument

RISK = Risk()
D = Decimal


def size(
    *,
    entry: str = "100",
    stop: str = "95",
    equity: str = "100000",
    cash: str = "100000",
    fx: str = "1",
    asset_class: AssetClass = AssetClass.EQUITY,
    small_cap: bool = False,
) -> tuple[int, SizingLimit]:
    result = size_position(
        instrument=instrument(asset_class=asset_class, small_cap=small_cap),
        equity=D(equity),
        free_cash=D(cash),
        entry=D(entry),
        stop=D(stop),
        fx_to_base=D(fx),
        risk=RISK,
    )
    return result.quantity, result.binding_limit


def test_risk_to_stop_binds_for_wide_stop() -> None:
    # 0.75 % of 100 000 = 750 risk; 750 / 15 per share = 50 shares
    assert size(stop="85") == (50, SizingLimit.TRADE_RISK)


def test_position_cap_binds_for_tight_stop() -> None:
    # 10 % of 100 000 = 10 000 -> 100 shares at 100
    assert size(stop="99") == (100, SizingLimit.POSITION_CAP)


def test_small_cap_and_crypto_have_lower_caps() -> None:
    assert size(stop="99", small_cap=True) == (50, SizingLimit.POSITION_CAP)
    assert size(stop="99", asset_class=AssetClass.CRYPTO) == (50, SizingLimit.POSITION_CAP)


def test_cash_binds() -> None:
    assert size(stop="99", cash="2550") == (25, SizingLimit.CASH)
    assert size(cash="-10") == (0, SizingLimit.CASH)


def test_fx_conversion() -> None:
    # 10 SEK per USD: 10 000 SEK cap / 1 000 SEK per share = 10 shares
    assert size(stop="99", fx="10") == (10, SizingLimit.POSITION_CAP)


def test_gap_loss_binds_when_gap_scenario_dominates() -> None:
    risk = Risk.model_validate({"gap": {"single_stock_gap_pct": 50}})
    result = size_position(
        instrument=instrument(),
        equity=D(100000),
        free_cash=D(100000),
        entry=D(100),
        stop=D(99),
        fx_to_base=D(1),
        risk=risk,
    )
    # 3 % of 100 000 = 3 000; 50 per share in the gap -> 60 shares
    assert (result.quantity, result.binding_limit) == (60, SizingLimit.GAP_LOSS)


def test_gap_loss_uses_stop_distance_when_larger() -> None:
    assert gap_loss_per_unit(D(100), D(60), D("0.25")) == D(40)
    assert gap_loss_per_unit(D(100), D(90), D("0.25")) == D(25)


def test_zero_equity_gives_zero() -> None:
    assert size(equity="0")[0] == 0


@pytest.mark.parametrize(
    ("entry", "stop", "fx"),
    [
        ("100", "100", "1"),
        ("100", "101", "1"),
        ("100", "0", "1"),
        ("0", "-1", "1"),
        ("1", "0.5", "0"),
    ],
)
def test_invalid_inputs(entry: str, stop: str, fx: str) -> None:
    with pytest.raises(ValueError, match=r"positive|below"):
        size(entry=entry, stop=stop, fx=fx)


prices = st.decimals(min_value=D("0.5"), max_value=D(5000), places=2)


@given(
    entry=prices,
    stop_fraction=st.decimals(min_value=D("0.01"), max_value=D("0.99"), places=2),
    equity=st.decimals(min_value=D(1000), max_value=D(10**8), places=2),
    cash_fraction=st.decimals(min_value=D(0), max_value=D(1), places=2),
    fx=st.decimals(min_value=D("0.01"), max_value=D(20), places=4),
    asset_class=st.sampled_from(list(AssetClass)),
    small_cap=st.booleans(),
)
def test_sized_position_always_respects_every_limit(
    entry: Decimal,
    stop_fraction: Decimal,
    equity: Decimal,
    cash_fraction: Decimal,
    fx: Decimal,
    asset_class: AssetClass,
    small_cap: bool,
) -> None:
    stop = entry * stop_fraction
    cash = equity * cash_fraction
    qty, _ = size(
        entry=str(entry),
        stop=str(stop),
        equity=str(equity),
        cash=str(cash),
        fx=str(fx),
        asset_class=asset_class,
        small_cap=small_cap,
    )
    assert qty >= 0
    value = qty * entry * fx
    assert qty * (entry - stop) * fx <= equity * D("0.0075")
    cap = D("0.05") if asset_class is AssetClass.CRYPTO or small_cap else D("0.10")
    assert value <= equity * cap
    gap = D("0.40") if asset_class is AssetClass.CRYPTO else D("0.25")
    assert qty * max(entry * gap, entry - stop) * fx <= equity * D("0.03")
    assert value <= cash
