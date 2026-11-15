"""Broker-neutral order types and errors (spec §8)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from jarvis.domain import Instrument, Side


class OrderStatus(StrEnum):
    """§8: new → submitted → partially_filled → filled | cancelled | rejected | expired."""

    NEW = "new"
    SUBMITTED = "submitted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"

    @property
    def is_terminal(self) -> bool:
        return self in _TERMINAL

    @property
    def is_working(self) -> bool:
        return self in (OrderStatus.SUBMITTED, OrderStatus.PARTIALLY_FILLED)


_TERMINAL = frozenset(
    {OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED, OrderStatus.EXPIRED}
)


@dataclass(frozen=True, slots=True)
class OrderRequest:
    """A limit order. With ``stop_price`` (and optionally ``take_profit_price``) it is a
    bracket: the broker holds the protective stop, so it works even if Jarvis is down.

    ``client_order_id`` is chosen by Jarvis and makes submission idempotent (§8).
    """

    client_order_id: str
    instrument: Instrument
    side: Side
    quantity: int
    limit_price: Decimal
    stop_price: Decimal | None = None
    take_profit_price: Decimal | None = None

    def __post_init__(self) -> None:
        if not self.client_order_id:
            raise ValueError("client_order_id is required")
        if self.quantity <= 0 or self.limit_price <= 0:
            raise ValueError("quantity and limit price must be positive")
        if self.side is Side.SELL and (self.stop_price or self.take_profit_price):
            raise ValueError("brackets are only for long entries (Jarvis is long-only)")
        if self.stop_price is not None and not 0 < self.stop_price < self.limit_price:
            raise ValueError("stop must be positive and below the limit price")
        if self.take_profit_price is not None and (
            self.stop_price is None or self.take_profit_price <= self.limit_price
        ):
            raise ValueError("a take-profit needs a stop and must be above the limit price")

    @property
    def stop_order_id(self) -> str:
        return f"{self.client_order_id}.stop"

    @property
    def take_profit_order_id(self) -> str:
        return f"{self.client_order_id}.tp"


@dataclass(frozen=True, slots=True)
class BrokerOrder:
    """The broker's view of one order (a bracket's children are separate orders)."""

    client_order_id: str
    symbol: str
    side: Side
    quantity: int
    status: OrderStatus
    filled_quantity: int
    average_fill_price: Decimal | None
    limit_price: Decimal | None = None  # entries, exits and take-profits
    stop_price: Decimal | None = None  # protective stops: the trigger level
    parent_id: str | None = None
    reject_reason: str | None = None


@dataclass(frozen=True, slots=True)
class Fill:
    """One execution. ``fill_id`` is the broker's own id (IBKR execId), unique per fill, so
    the same fill can never be booked twice after a restart."""

    fill_id: str
    client_order_id: str
    symbol: str
    side: Side
    quantity: int
    price: Decimal
    commission: Decimal
    at: datetime


@dataclass(frozen=True, slots=True)
class BrokerPosition:
    symbol: str
    quantity: int
    average_cost: Decimal


class BrokerError(Exception):
    """Base class for broker failures."""


class BrokerUnavailableError(BrokerError):
    """No connection to the broker (gateway down, logged out or restarting)."""


class DuplicateOrderIdError(BrokerError):
    """A different order already uses this client order id. Nothing was sent."""
