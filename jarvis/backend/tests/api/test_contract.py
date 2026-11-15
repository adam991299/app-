from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from jarvis.api import contract
from jarvis.api.schemas import PortfolioOut, PositionOut


def test_checked_in_contract_is_current() -> None:
    assert contract.CONTRACT_PATH.read_text(encoding="utf-8") == contract.render(), (
        "run: uv run python -m jarvis.api.contract"
    )


def test_main_writes_the_contract(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "api.schema.json"
    monkeypatch.setattr(contract, "CONTRACT_PATH", target)
    assert contract.main() == 0
    assert json.loads(target.read_text(encoding="utf-8"))["title"] == "Jarvis API"


def test_money_is_serialised_as_exact_strings() -> None:
    position = PositionOut(
        symbol="AAPL",
        quantity=3,
        currency="USD",
        average_price=Decimal("187.10"),
        last_price=None,
        market_value=None,
        unrealized_pnl=None,
        unrealized_pnl_pct=None,
        stop_price=Decimal("170.0000001"),
        strategy=None,
    )
    out = PortfolioOut(
        base_currency="SEK",
        net_liquidation=Decimal("100000.10"),
        cash=None,
        day_change=None,
        day_change_pct=None,
        positions=[position],
        as_of=datetime(2026, 11, 16, tzinfo=UTC),
    )
    data = json.loads(out.model_dump_json())
    assert data["net_liquidation"] == "100000.10"
    assert data["positions"][0]["stop_price"] == "170.0000001"
    assert data["cash"] is None
