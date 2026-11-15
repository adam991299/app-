from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from jarvis.domain import AssetClass, Instrument, Position, Quote
from tests.factories import NOW, instrument


@pytest.mark.parametrize(
    ("symbol", "exchange", "currency"),
    [("", "SMART", "USD"), ("AAPL", "", "USD"), ("AAPL", "SMART", "usd"), ("AAPL", "SMART", "US")],
)
def test_instrument_validation(symbol: str, exchange: str, currency: str) -> None:
    with pytest.raises(ValueError, match=r"instrument|currency"):
        Instrument(symbol, exchange, currency, AssetClass.EQUITY)


@pytest.mark.parametrize(("last", "fx"), [("0", "1"), ("-1", "1"), ("10", "0")])
def test_quote_needs_positive_prices(last: str, fx: str) -> None:
    with pytest.raises(ValueError, match="positive"):
        Quote("AAPL", Decimal(last), Decimal(fx), NOW)


def test_quote_needs_timezone() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        Quote("AAPL", Decimal(1), Decimal(1), datetime(2026, 1, 1))  # noqa: DTZ001


def test_quote_value_in_base_currency() -> None:
    assert Quote("AAPL", Decimal("200"), Decimal("10.5"), NOW).last_base == Decimal("2100.0")


@pytest.mark.parametrize(("quantity", "price"), [(0, "10"), (-5, "10"), (5, "0")])
def test_position_validation(quantity: int, price: str) -> None:
    with pytest.raises(ValueError, match="positive"):
        Position(instrument(), quantity, Decimal(price), None)
