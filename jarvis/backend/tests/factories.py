"""Builders for test data. Defaults describe a healthy account in an open market."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from jarvis.config.settings import Risk
from jarvis.domain import Account, AssetClass, Instrument, Position, Quote, Side
from jarvis.risk.breakers import BreakerStatus, TradingState
from jarvis.risk.engine import MarketSession, OrderProposal, PendingOrder, RiskContext

NOW = datetime(2026, 11, 16, 16, 0, tzinfo=UTC)  # a Monday, mid-session in New York
RISK = Risk()


def instrument(
    symbol: str = "AAPL",
    *,
    asset_class: AssetClass = AssetClass.EQUITY,
    sector: str | None = "technology",
    small_cap: bool = False,
) -> Instrument:
    return Instrument(symbol, "SMART", "USD", asset_class, sector, small_cap)


def quote(symbol: str = "AAPL", last: str = "100", *, fx: str = "1", age_s: int = 0) -> Quote:
    return Quote(symbol, Decimal(last), Decimal(fx), NOW - timedelta(seconds=age_s))


def position(inst: Instrument, quantity: int, price: str = "100") -> Position:
    return Position(inst, quantity, Decimal(price), Decimal(price) * Decimal("0.9"))


def buy(
    inst: Instrument | None = None,
    quantity: int = 10,
    limit: str = "100",
    stop: str | None = "95",
    *,
    edge: str | None = "100",
    cost: str = "5",
) -> OrderProposal:
    return OrderProposal(
        instrument=inst or instrument(),
        side=Side.BUY,
        quantity=quantity,
        limit_price=Decimal(limit),
        estimated_cost=Decimal(cost),
        stop_price=None if stop is None else Decimal(stop),
        expected_edge=None if edge is None else Decimal(edge),
    )


def sell(inst: Instrument | None = None, quantity: int = 10, limit: str = "100") -> OrderProposal:
    return OrderProposal(inst or instrument(), Side.SELL, quantity, Decimal(limit), Decimal(1))


def session(
    opens: datetime | None = NOW - timedelta(hours=1, minutes=30),
    closes: datetime | None = NOW + timedelta(hours=5),
) -> MarketSession:
    return MarketSession(opens, closes)


ACTIVE = BreakerStatus(TradingState.ACTIVE, (), kill_switch_should_engage=False)


def context(
    *,
    equity: str = "100000",
    cash: str | None = None,
    settled_cash: str | None = None,
    positions: Mapping[str, Position] | None = None,
    pending: Sequence[PendingOrder] = (),
    protected: Mapping[str, int] | None = None,
    quotes: Sequence[Quote] | None = None,
    market: MarketSession | None = None,
    breakers: BreakerStatus = ACTIVE,
    orders_last_minute: int = 0,
    orders_today: int = 0,
    now: datetime = NOW,
) -> RiskContext:
    return RiskContext(
        now=now,
        account=Account(
            Decimal(equity),
            Decimal(cash if cash is not None else equity),
            None if settled_cash is None else Decimal(settled_cash),
        ),
        positions=positions or {},
        pending=pending,
        protected=protected or {},
        quotes={q.symbol: q for q in (quotes if quotes is not None else [quote()])},
        session=market or session(),
        breakers=breakers,
        orders_last_minute=orders_last_minute,
        orders_today=orders_today,
    )
