"""The interface every broker implementation provides (IBKR, SimBroker, later others).

Rules for implementations:
- Every call either succeeds or raises ``BrokerError``; nothing fails silently.
- ``submit`` is idempotent: resubmitting the same request returns the existing order,
  a different request under the same id raises ``DuplicateOrderId``.
- A rejected order is returned with status ``REJECTED`` and a reason, not raised.
- The broker is the source of truth; callers reconcile against these methods (§8).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Protocol

from jarvis.broker.models import BrokerOrder, BrokerPosition, Fill, OrderRequest
from jarvis.domain import Account


class BrokerAdapter(Protocol):
    async def connect(self) -> None: ...

    async def disconnect(self) -> None: ...

    def is_connected(self) -> bool: ...

    async def account(self) -> Account: ...

    async def positions(self) -> tuple[BrokerPosition, ...]: ...

    async def open_orders(self) -> tuple[BrokerOrder, ...]: ...

    async def order(self, client_order_id: str) -> BrokerOrder | None: ...

    async def submit(self, request: OrderRequest) -> BrokerOrder: ...

    async def cancel(self, client_order_id: str) -> BrokerOrder: ...

    async def modify_stop(self, client_order_id: str, stop_price: Decimal) -> BrokerOrder:
        """Move a working protective stop to a new trigger price."""
        ...

    async def fills(self, since: datetime) -> tuple[Fill, ...]: ...
