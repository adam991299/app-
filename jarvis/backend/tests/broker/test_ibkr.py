"""IbkrBroker against a fake gateway built from ib_async's own data classes."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from ib_async import (
    AccountValue,
    CommissionReport,
    Contract,
    Execution,
    Order,
    OrderStatus,
    Position,
    Stock,
    Trade,
    TradeLogEntry,
)
from ib_async import Fill as IbFill

from jarvis.broker import (
    BrokerAdapter,
    BrokerError,
    BrokerUnavailableError,
    DuplicateOrderIdError,
    OrderRequest,
)
from jarvis.broker.ibkr import IbkrBroker, IbkrSettings
from jarvis.broker.models import OrderStatus as Status
from jarvis.domain import Side
from tests.factories import instrument

D = Decimal
NOW = datetime(2026, 11, 16, 16, tzinfo=UTC)
AAPL = instrument()
SETTINGS = IbkrSettings(
    host="ib-gateway", port=4004, client_id=7, account="DU123", settle_seconds=0.3
)


class ReqIds:
    def __init__(self) -> None:
        self.next = 100

    def getReqId(self) -> int:
        self.next += 1
        return self.next


@dataclass
class FakeIB:
    connected: bool = True
    refuse_connect: bool = False
    hang: bool = False
    client: ReqIds = field(default_factory=ReqIds)
    values: list[AccountValue] = field(default_factory=list)
    held: list[Position] = field(default_factory=list)
    all_trades: list[Trade] = field(default_factory=list)
    executions: list[IbFill] = field(default_factory=list)
    unknown_contracts: set[str] = field(default_factory=set)
    status_on_place: str = "Submitted"
    placed: list[Order] = field(default_factory=list)
    cancelled: list[Order] = field(default_factory=list)

    async def connectAsync(
        self,
        host: str,
        port: int,
        clientId: int,
        timeout: float,
        account: str,
    ) -> None:
        if self.refuse_connect:
            raise ConnectionRefusedError("gateway down")
        self.connected = True

    def disconnect(self) -> None:
        self.connected = False

    def isConnected(self) -> bool:
        return self.connected

    async def accountSummaryAsync(self, account: str) -> list[AccountValue]:
        if self.hang:
            await asyncio.sleep(60)
        return self.values

    def positions(self, account: str) -> list[Position]:
        return self.held

    def openTrades(self) -> list[Trade]:
        return [t for t in self.all_trades if not t.isDone()]

    def trades(self) -> list[Trade]:
        return self.all_trades

    def placeOrder(self, contract: Contract, order: Order) -> Trade:
        self.placed.append(order)
        for trade in self.all_trades:
            if trade.order.orderId == order.orderId:
                return trade  # a modification of an existing order
        trade = Trade(
            contract=contract,
            order=order,
            orderStatus=OrderStatus(orderId=order.orderId, status=self.status_on_place),
        )
        self.all_trades.append(trade)
        return trade

    def cancelOrder(self, order: Order) -> None:
        self.cancelled.append(order)
        for trade in self.all_trades:
            if trade.order.orderId == order.orderId:
                trade.orderStatus.status = "Cancelled"

    async def reqExecutionsAsync(self) -> list[IbFill]:
        return self.executions

    async def qualifyContractsAsync(self, *contracts: Contract) -> list[Contract | None]:
        return [None if c.symbol in self.unknown_contracts else c for c in contracts]


async def no_sleep(_: float) -> None:
    await asyncio.sleep(0)


def setup(**kwargs: Any) -> tuple[FakeIB, IbkrBroker]:
    ib = FakeIB(**kwargs)
    return ib, IbkrBroker(ib, SETTINGS, sleep=no_sleep)


def bracket(cid: str = "trend:AAPL:1", tp: str | None = None) -> OrderRequest:
    return OrderRequest(
        cid, AAPL, Side.BUY, 10, D("100.20"), D("95.00"), None if tp is None else D(tp)
    )


def fill(trade: Trade, qty: float, price: float) -> None:
    trade.orderStatus.filled += qty
    trade.orderStatus.avgFillPrice = price
    if trade.orderStatus.filled >= trade.order.totalQuantity:
        trade.orderStatus.status = "Filled"


def by_ref(ib: FakeIB, ref: str) -> Trade:
    return next(t for t in ib.all_trades if t.order.orderRef == ref)


def test_satisfies_the_adapter_protocol() -> None:
    _, broker = setup()
    adapter: BrokerAdapter = broker
    assert adapter.is_connected()


# -- connection ----------------------------------------------------------------------


async def test_connect_and_disconnect() -> None:
    _, broker = setup(connected=False)
    await broker.connect()
    assert broker.is_connected()
    await broker.connect()  # already connected: nothing happens
    await broker.disconnect()
    assert not broker.is_connected()


async def test_gateway_down_is_an_outage() -> None:
    _, broker = setup(connected=False, refuse_connect=True)
    with pytest.raises(BrokerUnavailableError, match="did not answer"):
        await broker.connect()


async def test_every_call_needs_a_connection() -> None:
    _, broker = setup(connected=False)
    for call in (
        broker.account(),
        broker.positions(),
        broker.open_orders(),
        broker.order("x"),
        broker.submit(bracket()),
        broker.cancel("x"),
        broker.modify_stop("x", D(1)),
        broker.fills(NOW),
    ):
        with pytest.raises(BrokerUnavailableError, match="not connected"):
            await call


async def test_slow_gateway_times_out() -> None:
    ib = FakeIB(hang=True)
    broker = IbkrBroker(ib, IbkrSettings("h", 1, 1, "DU1", timeout_seconds=0.05))
    with pytest.raises(BrokerUnavailableError):
        await broker.account()


# -- account and positions -------------------------------------------------------------


async def test_account_in_base_currency() -> None:
    _, broker = setup(
        values=[
            AccountValue("DU123", "NetLiquidation", "100482.35", "SEK", ""),
            AccountValue("DU123", "TotalCashValue", "81250.1", "SEK", ""),
            AccountValue("DU123", "NetLiquidation", "9400", "USD", ""),
            AccountValue("DU123", "BuyingPower", "1", "SEK", ""),
        ]
    )
    account = await broker.account()
    assert (account.net_liquidation, account.cash) == (D("100482.35"), D("81250.1"))


async def test_incomplete_account_summary_is_refused() -> None:
    _, broker = setup(values=[AccountValue("DU123", "NetLiquidation", "1", "SEK", "")])
    with pytest.raises(BrokerError, match="missing"):
        await broker.account()


async def test_positions() -> None:
    _, broker = setup(
        held=[
            Position("DU123", Stock("MSFT", "SMART", "USD"), 12.0, 512.4),
            Position("DU123", Stock("AAPL", "SMART", "USD"), 5.0, 100.1),
            Position("DU123", Stock("XOM", "SMART", "USD"), 0.0, 0.0),
        ]
    )
    positions = await broker.positions()
    assert [(p.symbol, p.quantity, p.average_cost) for p in positions] == [
        ("AAPL", 5, D("100.1")),
        ("MSFT", 12, D("512.4")),
    ]


async def test_fractional_shares_are_refused() -> None:
    _, broker = setup(held=[Position("DU123", Stock("MSFT", "SMART", "USD"), 1.5, 1.0)])
    with pytest.raises(BrokerError, match="fractional"):
        await broker.positions()


# -- placing orders ----------------------------------------------------------------------


async def test_bracket_is_sent_as_one_unit_with_refs() -> None:
    ib, broker = setup()
    view = await broker.submit(bracket(tp="120.00"))
    assert (view.client_order_id, view.status, view.limit_price) == (
        "trend:AAPL:1",
        Status.SUBMITTED,
        D("100.2"),
    )
    parent, tp, stop = ib.placed
    assert (parent.orderRef, parent.tif, parent.transmit, parent.account) == (
        "trend:AAPL:1",
        "DAY",
        False,
        "DU123",
    )
    assert (tp.orderRef, tp.parentId, tp.tif, tp.transmit) == (
        "trend:AAPL:1.tp",
        parent.orderId,
        "GTC",
        False,
    )
    assert (stop.orderRef, stop.orderType, stop.auxPrice, stop.transmit) == (
        "trend:AAPL:1.stop",
        "STP",
        95.0,
        True,
    )
    stop_view = await broker.order("trend:AAPL:1.stop")
    assert stop_view is not None
    assert (stop_view.parent_id, stop_view.stop_price, stop_view.side) == (
        "trend:AAPL:1",
        D("95.0"),
        Side.SELL,
    )


async def test_plain_exit_is_transmitted_alone() -> None:
    ib, broker = setup()
    await broker.submit(OrderRequest("x", AAPL, Side.SELL, 5, D("101.00")))
    (only,) = ib.placed
    assert (only.action, only.transmit) == ("SELL", True)


async def test_resubmitting_returns_the_existing_order() -> None:
    ib, broker = setup()
    await broker.submit(bracket())
    again = await broker.submit(bracket())
    assert again.client_order_id == "trend:AAPL:1"
    assert len(ib.placed) == 2  # parent + stop, once


async def test_reused_id_for_a_different_order_is_refused() -> None:
    _, broker = setup()
    await broker.submit(bracket())
    other = OrderRequest("trend:AAPL:1", AAPL, Side.BUY, 11, D("100.20"), D("95.00"))
    with pytest.raises(DuplicateOrderIdError):
        await broker.submit(other)


async def test_off_tick_prices_and_unknown_contracts_are_refused() -> None:
    ib, broker = setup(unknown_contracts={"AAPL"})
    off_tick = OrderRequest("y", AAPL, Side.BUY, 1, D("100.205"), D("95.00"))
    with pytest.raises(BrokerError, match="tick"):
        await broker.submit(off_tick)
    with pytest.raises(BrokerError, match="does not know"):
        await broker.submit(bracket())
    assert ib.placed == []


async def test_waits_for_acknowledgement_then_returns() -> None:
    _, broker = setup(status_on_place="PendingSubmit")
    view = await broker.submit(bracket())
    assert view.status is Status.SUBMITTED  # still pending; the next sync updates it


async def test_rejection_carries_ibkrs_message() -> None:
    ib, broker = setup(status_on_place="Inactive")
    await broker.submit(bracket())
    trade = by_ref(ib, "trend:AAPL:1")
    trade.log.append(TradeLogEntry(NOW, "Inactive", "Order rejected: no permission", 201))
    view = await broker.order("trend:AAPL:1")
    assert view is not None
    assert (view.status, view.reject_reason) == (Status.REJECTED, "Order rejected: no permission")
    trade.log.clear()
    silent = await broker.order("trend:AAPL:1")
    assert silent is not None
    assert silent.reject_reason == "rejected by IBKR"


# -- status mapping ----------------------------------------------------------------------


async def test_partial_and_full_fills() -> None:
    ib, broker = setup()
    await broker.submit(bracket())
    trade = by_ref(ib, "trend:AAPL:1")
    fill(trade, 4, 100.1)
    view = await broker.order("trend:AAPL:1")
    assert view is not None
    assert (view.status, view.filled_quantity, view.average_fill_price) == (
        Status.PARTIALLY_FILLED,
        4,
        D("100.1"),
    )
    fill(trade, 6, 100.15)
    view = await broker.order("trend:AAPL:1")
    assert view is not None
    assert view.status is Status.FILLED
    assert [o.client_order_id for o in await broker.open_orders()] == ["trend:AAPL:1.stop"]


async def test_unknown_status_is_refused_not_guessed() -> None:
    ib, broker = setup()
    await broker.submit(bracket())
    by_ref(ib, "trend:AAPL:1").orderStatus.status = "Mystery"
    with pytest.raises(BrokerError, match="unknown IBKR order status"):
        await broker.order("trend:AAPL:1")


async def test_orders_not_made_by_jarvis_get_a_foreign_id() -> None:
    ib, broker = setup()
    manual = Order(
        orderId=5, permId=999, action="BUY", totalQuantity=1, orderType="LMT", lmtPrice=10.0
    )
    ib.placeOrder(Stock("MSFT", "SMART", "USD"), manual)
    assert [o.client_order_id for o in await broker.open_orders()] == ["ibkr-999"]
    assert await broker.order("missing") is None


async def test_missing_price_is_refused() -> None:
    ib, broker = setup()
    odd = Order(
        orderId=6, orderRef="odd", action="BUY", totalQuantity=1, orderType="LMT", lmtPrice=None
    )
    ib.placeOrder(Stock("MSFT", "SMART", "USD"), odd)
    with pytest.raises(BrokerError, match="without a price"):
        await broker.order("odd")


# -- cancel and modify -------------------------------------------------------------------


async def test_cancel() -> None:
    ib, broker = setup()
    await broker.submit(bracket())
    view = await broker.cancel("trend:AAPL:1")
    assert view.status is Status.CANCELLED
    again = await broker.cancel("trend:AAPL:1")  # already done: no second request
    assert again.status is Status.CANCELLED
    assert len(ib.cancelled) == 1
    with pytest.raises(BrokerError, match="unknown order"):
        await broker.cancel("nope")


async def test_raising_the_stop_modifies_the_same_order() -> None:
    ib, broker = setup()
    await broker.submit(bracket())
    stop = by_ref(ib, "trend:AAPL:1.stop")
    view = await broker.modify_stop("trend:AAPL:1.stop", D("97.50"))
    assert view.stop_price == D("97.5")
    assert ib.placed[-1].orderId == stop.order.orderId
    assert len(ib.all_trades) == 2


@pytest.mark.parametrize(
    ("ref", "price", "match"),
    [
        ("trend:AAPL:1", "97", "no protective stop"),
        ("nope", "97", "no protective stop"),
        ("trend:AAPL:1.stop", "97.505", "tick"),
        ("trend:AAPL:1.stop", "0", "positive"),
    ],
)
async def test_modify_stop_refusals(ref: str, price: str, match: str) -> None:
    _, broker = setup()
    await broker.submit(bracket())
    with pytest.raises(BrokerError, match=match):
        await broker.modify_stop(ref, D(price))


async def test_finished_stop_cannot_be_moved() -> None:
    ib, broker = setup()
    await broker.submit(bracket())
    by_ref(ib, "trend:AAPL:1.stop").orderStatus.status = "Filled"
    with pytest.raises(BrokerError, match="no longer working"):
        await broker.modify_stop("trend:AAPL:1.stop", D(97))


# -- fills -------------------------------------------------------------------------------


def execution(
    exec_id: str, ref: str, side: str, at: datetime, commission: float | None, perm: int = 1
) -> IbFill:
    report = (
        CommissionReport(execId=exec_id, commission=commission)
        if commission is not None
        else CommissionReport()
    )
    return IbFill(
        Stock("AAPL", "SMART", "USD"),
        Execution(
            execId=exec_id, time=at, side=side, shares=10.0, price=100.15, orderRef=ref, permId=perm
        ),
        report,
        at,
    )


async def test_fills_wait_for_commission_and_respect_since() -> None:
    ib, broker = setup()
    ib.executions = [
        execution("e2", "trend:AAPL:1.stop", "SLD", NOW + timedelta(hours=1), 1.0),
        execution("e1", "trend:AAPL:1", "BOT", NOW, 1.25),
        execution("e3", "trend:AAPL:2", "BOT", NOW, None),  # commission not known yet
        execution("e0", "old", "BOT", NOW - timedelta(days=1), 1.0),
        execution("e4", "", "BOT", NOW, 1.0, perm=777),  # not made by Jarvis
    ]
    fills = await broker.fills(NOW)
    assert [(f.fill_id, f.client_order_id, f.side, f.commission) for f in fills] == [
        ("e1", "trend:AAPL:1", Side.BUY, D("1.25")),
        ("e4", "ibkr-777", Side.BUY, D("1.0")),
        ("e2", "trend:AAPL:1.stop", Side.SELL, D("1.0")),
    ]
    assert fills[0].price == D("100.15")
    assert fills[0].quantity == 10
