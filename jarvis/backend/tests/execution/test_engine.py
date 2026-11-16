"""Execution against the SimBroker and a real database, including crash scenarios."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest

from jarvis.broker import (
    BrokerError,
    BrokerOrder,
    BrokerUnavailableError,
    OrderRequest,
    OrderStatus,
)
from jarvis.broker.sim import SimBroker
from jarvis.config.settings import Risk
from jarvis.domain import Instrument, Quote, Side
from jarvis.execution.alerts import AlertLevel
from jarvis.execution.engine import EntrySignal, ExecutionEngine, Outcome
from jarvis.risk.breakers import TradingState
from jarvis.risk.engine import MarketSession
from jarvis.risk.reasons import Reason
from jarvis.store.repo import NewOrder, Store
from tests.factories import NOW, instrument

D = Decimal
AAPL = instrument()
MSFT = instrument("MSFT")


@dataclass
class Recorder:
    sent: list[tuple[AlertLevel, str]] = field(default_factory=list)
    failing: bool = False

    async def send(self, level: AlertLevel, message_sv: str) -> None:
        if self.failing:
            raise RuntimeError("push service down")
        self.sent.append((level, message_sv))


class Clock:
    def __init__(self) -> None:
        self.now = NOW

    def __call__(self) -> datetime:
        return self.now


class FlakySim(SimBroker):
    """A SimBroker whose next submit can fail or be squeezed for cash."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.fail_submit = False
        self.drain_cash_on_submit = False

    async def submit(self, request: OrderRequest) -> BrokerOrder:
        if self.fail_submit:
            self.fail_submit = False
            raise BrokerUnavailableError("connection reset")
        if self.drain_cash_on_submit:
            self._cash = D(10)
        return await super().submit(request)


@dataclass
class World:
    sim: FlakySim
    store: Store
    engine: ExecutionEngine
    alerts: Recorder
    clock: Clock
    prices: dict[str, Decimal]

    def price(self, symbol: str, value: str) -> None:
        self.prices[symbol] = D(value)
        self.sim.set_price(symbol, D(value))


@pytest.fixture
async def world(store: Store) -> World:
    clock = Clock()
    sim = FlakySim(cash=D(100000), clock=clock)
    await sim.connect()
    prices: dict[str, Decimal] = {}
    alerts = Recorder()

    async def quotes(inst: Instrument) -> Quote | None:
        price = prices.get(inst.symbol)
        return None if price is None else Quote(inst.symbol, price, D(1), clock.now)

    def sessions(_: Instrument, now: datetime) -> MarketSession:
        return MarketSession(now - timedelta(hours=2), now + timedelta(hours=4))

    engine = ExecutionEngine(
        broker=sim,
        store=store,
        risk=Risk(),
        instruments={"AAPL": AAPL},
        quotes=quotes,
        sessions=sessions,
        clock=clock,
        clock_drift=lambda: 0.0,
        alerts=alerts,
    )
    w = World(sim, store, engine, alerts, clock, prices)
    w.price("AAPL", "100")
    assert await engine.recover()
    return w


def signal(sid: str = "trend:AAPL:2026-11-16", **kw: Any) -> EntrySignal:
    base: dict[str, Any] = {
        "signal_id": sid,
        "strategy": "trend",
        "instrument": AAPL,
        "quantity": 50,
        "limit_price": D("100.2"),
        "stop_price": D(95),
        "expected_edge": D(500),
        "estimated_cost": D(5),
        "explanation_sv": "Kursen bröt över 50-dagarshögsta.",
        "features": {"donchian_high": "100.1"},
    }
    return EntrySignal(**(base | kw))


async def status_of(store: Store, cid: str) -> OrderStatus:
    return (await store.known_order(cid)).status


# -- the normal path ----------------------------------------------------------------------


async def test_entry_is_risk_checked_journaled_sent_and_protected(world: World) -> None:
    result = await world.engine.submit_entry(signal())
    assert result.outcome is Outcome.SUBMITTED
    cid = result.client_order_id
    assert await status_of(world.store, cid) is OrderStatus.FILLED
    stop = await world.store.known_order(f"{cid}.stop")
    assert (stop.status, stop.stop_price, stop.quantity) == (OrderStatus.SUBMITTED, D(95), 50)
    assert await world.store.risk_decisions(cid) == [(True, [])]
    assert await world.engine.reconcile()
    assert await world.store.booked_positions() == {"AAPL": 50}
    assert world.alerts.sent == []


async def test_take_profit_is_journaled_and_tracked(world: World) -> None:
    result = await world.engine.submit_entry(signal(take_profit_price=D(120)))
    tp = await world.store.known_order(f"{result.client_order_id}.tp")
    assert (tp.kind, tp.limit_price, tp.status) == ("take_profit", D(120), OrderStatus.SUBMITTED)
    world.price("AAPL", "121")
    assert await world.engine.reconcile()
    assert await world.store.booked_positions() == {}
    assert await status_of(world.store, f"{result.client_order_id}.stop") is OrderStatus.CANCELLED


async def test_replayed_signal_is_never_sent_twice(world: World) -> None:
    first = await world.engine.submit_entry(signal())
    again = await world.engine.submit_entry(signal())
    assert again.outcome is Outcome.DUPLICATE
    assert again.client_order_id == first.client_order_id
    assert len(await world.sim.fills(NOW - timedelta(days=1))) == 1


async def test_invalid_signal_id_is_refused(world: World) -> None:
    with pytest.raises(ValueError, match="invalid signal id"):
        await world.engine.submit_entry(signal("has spaces"))


# -- risk and broker rejections -------------------------------------------------------------


async def test_risk_rejection_is_logged_and_nothing_is_sent(world: World) -> None:
    result = await world.engine.submit_entry(signal(quantity=500))
    assert result.outcome is Outcome.REJECTED_BY_RISK
    assert Reason.POSITION_LIMIT in result.reasons
    assert await world.store.order(result.client_order_id) is None
    approved, reasons = (await world.store.risk_decisions(result.client_order_id))[0]
    assert not approved
    assert "position_limit" in reasons
    assert await world.sim.open_orders() == ()


async def test_no_trading_before_first_reconciliation(store: Store) -> None:
    clock = Clock()
    sim = SimBroker(cash=D(1000), clock=clock)
    await sim.connect()

    async def no_quotes(_: Instrument) -> Quote | None:
        return None

    engine = ExecutionEngine(
        broker=sim,
        store=store,
        risk=Risk(),
        instruments={"AAPL": AAPL},
        quotes=no_quotes,
        sessions=lambda _i, n: MarketSession(n, n + timedelta(hours=1)),
        clock=clock,
        clock_drift=lambda: 0.0,
        alerts=Recorder(),
    )
    status = await engine.trading_status(NOW)
    assert status.state is TradingState.HALTED
    result = await engine.submit_entry(signal())
    assert result.outcome is Outcome.REJECTED_BY_RISK
    assert Reason.NOT_RECONCILED in result.reasons


async def test_broker_rejection_is_recorded(world: World) -> None:
    world.sim.drain_cash_on_submit = True
    result = await world.engine.submit_entry(signal())
    assert result.outcome is Outcome.REJECTED_BY_BROKER
    assert result.detail is not None
    assert "cash" in result.detail
    assert await status_of(world.store, result.client_order_id) is OrderStatus.REJECTED


async def test_reused_id_at_broker_halts_and_alerts(world: World) -> None:
    await world.sim.submit(OrderRequest("trend:AAPL:x", AAPL, Side.BUY, 1, D(100), D(90)))
    result = await world.engine.submit_entry(signal("trend:AAPL:x"))
    assert result.outcome is Outcome.REJECTED_BY_BROKER
    assert world.alerts.sent[0][0] is AlertLevel.CRITICAL
    assert world.engine.health().positions_reconciled is False


# -- crashes and outages ------------------------------------------------------------------------


async def test_crash_between_journal_and_send_is_cleaned_up_on_recovery(world: World) -> None:
    world.sim.fail_submit = True
    result = await world.engine.submit_entry(signal())
    assert result.outcome is Outcome.BROKER_UNAVAILABLE
    assert await status_of(world.store, result.client_order_id) is OrderStatus.NEW
    assert await world.engine.recover()
    assert await status_of(world.store, result.client_order_id) is OrderStatus.CANCELLED
    assert await status_of(world.store, f"{result.client_order_id}.stop") is OrderStatus.CANCELLED
    assert await world.sim.positions() == ()


async def test_journaled_but_unsent_signal_can_be_retried(world: World) -> None:
    world.sim.fail_submit = True
    first = await world.engine.submit_entry(signal())
    retry = await world.engine.submit_entry(signal())
    assert first.outcome is Outcome.BROKER_UNAVAILABLE
    assert retry.outcome is Outcome.SUBMITTED
    assert await world.store.risk_decisions(retry.client_order_id) == [(True, []), (True, [])]


async def test_crash_after_broker_accepted_is_recovered_from_the_broker(world: World) -> None:
    """Journaled and accepted by the broker, but Jarvis died before recording it."""
    cid = "trend:AAPL:crash"
    await world.store.add_order(
        NewOrder(cid, "entry", "AAPL", "buy", 10, D(100), D(95), strategy="trend"), at=NOW
    )
    await world.store.add_order(
        NewOrder(f"{cid}.stop", "stop", "AAPL", "sell", 10, None, D(95), parent_id=cid), at=NOW
    )
    await world.sim.submit(OrderRequest(cid, AAPL, Side.BUY, 10, D(100), D(95)))
    assert await world.engine.recover()
    assert await status_of(world.store, cid) is OrderStatus.FILLED
    assert await world.store.booked_positions() == {"AAPL": 10}


async def test_broker_outage_stops_trading_after_repeated_errors(world: World) -> None:
    for _ in range(5):
        world.sim.fail_next_call(BrokerUnavailableError("timeout"))
        result = await world.engine.submit_entry(signal())
        assert result.outcome is Outcome.BROKER_UNAVAILABLE
    assert world.engine.health().consecutive_broker_errors == 5
    status = await world.engine.trading_status(NOW)
    assert status.state is TradingState.HALTED
    assert Reason.BROKER_ERRORS in status.reasons
    assert await world.engine.reconcile()  # a successful call resets the count
    assert world.engine.health().consecutive_broker_errors == 0


async def test_gateway_disconnect_halts_and_stops_still_protect(world: World) -> None:
    await world.engine.submit_entry(signal())
    world.sim.go_offline()
    world.price("AAPL", "94")  # the market falls while Jarvis is cut off
    assert not await world.engine.reconcile()
    assert (await world.engine.trading_status(NOW)).state is TradingState.HALTED
    world.sim.go_online()
    await world.sim.connect()
    assert await world.engine.reconcile()
    assert await world.store.booked_positions() == {}


async def test_recover_and_reconcile_report_broker_errors(world: World) -> None:
    world.sim.fail_submit = True
    await world.engine.submit_entry(signal())
    world.sim.fail_next_call(BrokerUnavailableError("down"))
    assert not await world.engine.recover()
    world.sim.fail_next_call(BrokerUnavailableError("down"))
    assert not await world.engine.reconcile()


# -- raising stops ----------------------------------------------------------------------------


async def test_stop_is_raised_never_lowered(world: World) -> None:
    cid = (await world.engine.submit_entry(signal())).client_order_id
    raised = await world.engine.raise_stop(cid, D(97))
    assert raised.outcome is Outcome.STOP_RAISED
    assert (await world.store.known_order(f"{cid}.stop")).stop_price == D(97)
    lower = await world.engine.raise_stop(cid, D(96))
    assert (lower.outcome, lower.detail) == (Outcome.STOP_UNCHANGED, "a stop is never lowered")
    through = await world.engine.raise_stop(cid, D(100))
    assert through.detail == "new stop not below the price"
    world.price("AAPL", "96.5")
    assert await world.engine.reconcile()
    assert await world.store.booked_positions() == {}
    gone = await world.engine.raise_stop(cid, D(98))
    assert gone.detail == "no working stop"


async def test_raise_stop_needs_a_quote_and_a_broker(world: World) -> None:
    cid = (await world.engine.submit_entry(signal())).client_order_id
    world.prices.pop("AAPL")
    assert (await world.engine.raise_stop(cid, D(97))).outcome is Outcome.STOP_UNCHANGED
    world.price("AAPL", "100")
    world.sim.fail_next_call(BrokerUnavailableError("down"))
    assert (await world.engine.raise_stop(cid, D(97))).outcome is Outcome.BROKER_UNAVAILABLE
    assert (await world.engine.raise_stop("nothing", D(97))).outcome is Outcome.STOP_UNCHANGED


async def test_raise_stop_for_unknown_instrument_does_nothing(world: World) -> None:
    await world.store.add_order(NewOrder("z", "entry", "ZZZ", "buy", 1, D(1), D(0.5)), at=NOW)
    await world.store.add_order(
        NewOrder("z.stop", "stop", "ZZZ", "sell", 1, None, D("0.5"), parent_id="z"), at=NOW
    )
    assert (await world.engine.raise_stop("z", D("0.9"))).outcome is Outcome.STOP_UNCHANGED


# -- reconciliation catches what does not add up -------------------------------------------------


async def test_trade_jarvis_did_not_make_halts_once_and_alerts_once(world: World) -> None:
    await world.sim.submit(OrderRequest("manual-1", AAPL, Side.BUY, 5, D(100), D(90)))
    assert not await world.engine.reconcile()
    assert not await world.engine.reconcile()
    messages = [m for _, m in world.alerts.sent]
    assert any("inte gjort" in m for m in messages)
    assert any("stämmer inte" in m for m in messages)
    assert any("inte skapat" in m for m in messages)
    assert len(messages) == len(set(messages))  # no repeats on the second run


async def test_position_without_stop_halts(world: World) -> None:
    cid = (await world.engine.submit_entry(signal())).client_order_id
    await world.sim.cancel(f"{cid}.stop")
    assert not await world.engine.reconcile()
    assert "saknar fullt skydd" in world.alerts.sent[-1][1]
    assert (await world.engine.trading_status(NOW)).state is TradingState.HALTED


async def test_unknown_holding_blocks_new_trades(world: World) -> None:
    world.price("MSFT", "50")
    world.engine._instruments = {"AAPL": AAPL, "MSFT": MSFT}
    await world.engine.submit_entry(
        signal("trend:MSFT:1", instrument=MSFT, quantity=10, limit_price=D(50), stop_price=D(45))
    )
    world.engine._instruments = {"AAPL": AAPL}  # the data for MSFT disappears
    result = await world.engine.submit_entry(signal())
    assert result.outcome is Outcome.REJECTED_BY_RISK
    assert result.reasons == (Reason.NOT_RECONCILED,)
    assert not await world.engine.reconcile()
    assert any("saknar uppgifter" in m for _, m in world.alerts.sent)


async def test_unknown_resting_order_blocks_new_trades(world: World) -> None:
    world.price("MSFT", "50")
    await world.sim.submit(OrderRequest("m", MSFT, Side.BUY, 1, D(40), D(35)))
    result = await world.engine.submit_entry(signal())
    assert result.reasons == (Reason.NOT_RECONCILED,)


async def test_impossible_broker_report_halts(world: World) -> None:
    cid = (await world.engine.submit_entry(signal())).client_order_id
    await world.store.update_order(
        f"{cid}.stop",
        at=NOW,
        status=OrderStatus.FILLED,
        filled_quantity=50,
        average_fill_price=D(95),
    )
    assert not await world.engine.reconcile()
    assert any("går inte ihop" in m for _, m in world.alerts.sent)


async def test_order_missing_at_broker_halts(world: World) -> None:
    await world.store.add_order(NewOrder("lost", "entry", "AAPL", "buy", 1, D(100), D(95)), at=NOW)
    await world.store.update_order(
        "lost", at=NOW, status=OrderStatus.SUBMITTED, filled_quantity=0, average_fill_price=None
    )
    assert not await world.engine.reconcile()
    assert any("finns inte längre" in m for _, m in world.alerts.sent)


async def test_resolved_problem_resumes_trading(world: World) -> None:
    await world.store.add_order(NewOrder("lost", "entry", "AAPL", "buy", 1, D(100), D(95)), at=NOW)
    await world.store.update_order(
        "lost", at=NOW, status=OrderStatus.SUBMITTED, filled_quantity=0, average_fill_price=None
    )
    assert not await world.engine.reconcile()
    await world.store.update_order(
        "lost", at=NOW, status=OrderStatus.CANCELLED, filled_quantity=0, average_fill_price=None
    )
    assert await world.engine.reconcile()
    assert world.engine.health().positions_reconciled


async def test_two_brackets_on_one_symbol(world: World) -> None:
    await world.engine.submit_entry(signal("a", quantity=20, stop_price=D(95)))
    result = await world.engine.submit_entry(signal("b", quantity=20, stop_price=D(97)))
    assert result.outcome is Outcome.SUBMITTED
    assert await world.engine.reconcile()


# -- kill switch ----------------------------------------------------------------------------


async def test_drawdown_engages_kill_switch_and_alerts_once(world: World) -> None:
    await world.store.record_equity(
        at=NOW - timedelta(days=10), net_liquidation=D(120000), cash=D(120000)
    )
    status = await world.engine.trading_status(NOW)
    assert status.state is TradingState.KILL_SWITCH
    assert (await world.store.controls()).kill_switch_engaged
    await world.engine.trading_status(NOW)
    critical = [m for level, m in world.alerts.sent if level is AlertLevel.CRITICAL]
    assert len(critical) == 1
    assert "Kill switch" in critical[0]
    result = await world.engine.submit_entry(signal())
    assert Reason.KILL_SWITCH_ENGAGED in result.reasons


async def test_resting_entry_counts_against_limits(world: World) -> None:
    resting = await world.engine.submit_entry(signal("rest", quantity=60, limit_price=D(99)))
    assert await status_of(world.store, resting.client_order_id) is OrderStatus.SUBMITTED
    more = await world.engine.submit_entry(signal("more", quantity=60))
    assert Reason.POSITION_LIMIT in more.reasons  # 60 resting + 60 new > 10 % of equity
    assert await world.engine.reconcile()


async def test_recover_keeps_orders_that_reached_the_broker(world: World) -> None:
    await world.engine.submit_entry(signal())
    world.sim.fail_submit = True
    unsent = await world.engine.submit_entry(signal("unsent", quantity=10))
    assert unsent.outcome is Outcome.BROKER_UNAVAILABLE
    assert await world.engine.reconcile()  # an unsent journal entry alone is no problem
    assert await status_of(world.store, unsent.client_order_id) is OrderStatus.NEW
    assert await world.engine.recover()
    assert await world.store.booked_positions() == {"AAPL": 50}


# -- regression tests for defects found in review ------------------------------------------------


async def test_stop_of_a_resting_entry_does_not_count_as_protection(world: World) -> None:
    a = await world.engine.submit_entry(signal("a", quantity=20))
    await world.engine.submit_entry(signal("b", quantity=20, limit_price=D(99), stop_price=D(94)))
    await world.sim.cancel(f"{a.client_order_id}.stop")
    assert not await world.engine.reconcile()
    assert any("saknar fullt skydd" in m for _, m in world.alerts.sent)


async def test_partial_fill_is_protected_and_reconciles(store: Store, world: World) -> None:
    world.sim._max_fill = 15
    result = await world.engine.submit_entry(signal(quantity=40))
    assert await status_of(store, result.client_order_id) is OrderStatus.PARTIALLY_FILLED
    assert await world.engine.reconcile()  # 15 bought, 15 covered by the active stop
    world.sim.expire_day_orders()
    assert await world.engine.reconcile()
    assert await status_of(store, result.client_order_id) is OrderStatus.EXPIRED
    stop = await store.known_order(f"{result.client_order_id}.stop")
    assert (stop.quantity, stop.status) == (15, OrderStatus.SUBMITTED)


async def test_stop_is_compared_with_the_broker_not_the_journal(world: World) -> None:
    cid = (await world.engine.submit_entry(signal())).client_order_id
    await world.sim.modify_stop(f"{cid}.stop", D(98))  # journal still says 95 (crash window)
    lowered = await world.engine.raise_stop(cid, D(96))
    assert lowered.outcome is Outcome.STOP_UNCHANGED
    assert await world.engine.reconcile()
    assert (await world.store.known_order(f"{cid}.stop")).stop_price == D(98)  # adopted


async def test_failed_alert_is_retried_and_reconcile_completes(world: World) -> None:
    cid = (await world.engine.submit_entry(signal())).client_order_id
    await world.sim.cancel(f"{cid}.stop")
    world.alerts.failing = True
    assert not await world.engine.reconcile()
    assert world.alerts.sent == []
    world.alerts.failing = False
    assert not await world.engine.reconcile()
    assert len([m for _, m in world.alerts.sent if "saknar fullt skydd" in m]) == 1


async def test_id_collision_keeps_trading_halted(world: World) -> None:
    await world.sim.submit(OrderRequest("trend:AAPL:x", AAPL, Side.BUY, 1, D(100), D(90)))
    await world.engine.submit_entry(signal("trend:AAPL:x"))
    assert not await world.engine.reconcile()
    assert not await world.engine.reconcile()
    assert any("inte den jag skapade" in m for _, m in world.alerts.sent)
    journal = await world.store.known_order("trend:AAPL:x")
    assert journal.quantity == 50  # the foreign order was not adopted


@pytest.mark.parametrize(
    ("change", "text"),
    [({"symbol": "MSFT"}, "symbol"), ({"side": "sell"}, "riktning"), ({"quantity": 7}, "antal")],
)
async def test_identity_mismatches_are_detected(
    world: World, change: dict[str, Any], text: str
) -> None:
    base: dict[str, Any] = {"symbol": "AAPL", "side": "buy", "quantity": 10}
    row = base | change
    await world.store.add_order(
        NewOrder("odd", "entry", row["symbol"], row["side"], row["quantity"], D(100), D(95)),
        at=NOW,
    )
    await world.sim.submit(OrderRequest("odd", AAPL, Side.BUY, 10, D(100), D(95)))
    assert not await world.engine.reconcile()
    assert any(text in m for _, m in world.alerts.sent)


async def test_broker_refusals_are_not_counted_as_outage(world: World) -> None:
    world.sim.drain_cash_on_submit = True
    rejected = await world.engine.submit_entry(signal())
    cid = rejected.client_order_id
    assert await status_of(world.store, f"{cid}.stop") is OrderStatus.CANCELLED
    for _ in range(6):
        assert (await world.engine.raise_stop(cid, D(97))).outcome is Outcome.STOP_UNCHANGED
    world.sim.fail_next_call(BrokerError("refused"))
    with pytest.raises(BrokerError):
        await world.engine._call(world.sim.account())
    assert world.engine.health().consecutive_broker_errors == 0


async def test_replay_after_broker_accepted_reports_duplicate(world: World) -> None:
    cid = "trend:AAPL:crash2"
    await world.store.add_order(
        NewOrder(cid, "entry", "AAPL", "buy", 50, D("100.2"), D(95), strategy="trend"), at=NOW
    )
    await world.store.add_order(
        NewOrder(f"{cid}.stop", "stop", "AAPL", "sell", 50, None, D(95), parent_id=cid), at=NOW
    )
    await world.sim.submit(OrderRequest(cid, AAPL, Side.BUY, 50, D("100.2"), D(95)))
    replay = await world.engine.submit_entry(signal(cid))
    assert (replay.outcome, replay.detail) == (Outcome.DUPLICATE, "filled")
    world.sim.fail_submit = True
    await world.engine.submit_entry(signal("unsent2", quantity=10))
    world.sim.fail_next_call(BrokerUnavailableError("down"))
    assert (await world.engine.submit_entry(signal("unsent2", quantity=10))).outcome is (
        Outcome.BROKER_UNAVAILABLE
    )


async def test_changing_mismatch_alerts_only_once(world: World) -> None:
    await world.sim.submit(OrderRequest("manual-1", AAPL, Side.BUY, 5, D(100), D(90)))
    assert not await world.engine.reconcile()
    await world.sim.submit(OrderRequest("manual-2", AAPL, Side.BUY, 3, D(100), D(90)))
    assert not await world.engine.reconcile()
    assert len([m for _, m in world.alerts.sent if "stämmer inte" in m]) == 1


async def test_unreasonable_account_value_halts_without_poisoning_marks(world: World) -> None:
    world.sim._cash = D(0)
    assert not await world.engine.reconcile()
    assert any("orimligt kontovärde" in m for _, m in world.alerts.sent)
    marks = await world.store.equity_marks(NOW)
    assert marks is not None
    assert marks.day_low == D(100000)
    assert not (await world.store.controls()).kill_switch_engaged
    result = await world.engine.submit_entry(signal())
    assert result.outcome is Outcome.REJECTED_BY_RISK


async def test_raise_stop_reports_outage_when_reading_the_stop(world: World) -> None:
    cid = (await world.engine.submit_entry(signal())).client_order_id
    world.sim.fail_next_call(BrokerUnavailableError("down"))
    assert (await world.engine.raise_stop(cid, D(97))).outcome is Outcome.BROKER_UNAVAILABLE


async def test_outage_while_checking_stops_fails_reconcile(world: World) -> None:
    await world.engine.submit_entry(signal())
    calls = 0
    original = world.sim.order

    async def flaky(client_order_id: str) -> BrokerOrder | None:
        nonlocal calls
        calls += 1
        if calls > 2:
            raise BrokerUnavailableError("down")
        return await original(client_order_id)

    world.sim.order = flaky  # type: ignore[method-assign]
    assert not await world.engine.reconcile()


async def test_raise_stop_reports_outage_when_moving_the_stop(world: World) -> None:
    cid = (await world.engine.submit_entry(signal())).client_order_id

    async def down(client_order_id: str, stop_price: Decimal) -> BrokerOrder:
        raise BrokerUnavailableError("down")

    world.sim.modify_stop = down  # type: ignore[method-assign]
    assert (await world.engine.raise_stop(cid, D(97))).outcome is Outcome.BROKER_UNAVAILABLE


async def test_reconcile_publishes_the_account_state_for_the_app(world: World) -> None:
    await world.engine.submit_entry(signal())
    world.price("AAPL", "102")
    assert await world.engine.reconcile()
    stored = await world.store.account_state()
    assert stored is not None
    at, payload = stored
    assert at == NOW
    assert payload["trading_state"] == "active"
    assert payload["reconciled"] is True
    position = payload["positions"][0]
    assert position["symbol"] == "AAPL"
    assert position["quantity"] == 50
    assert position["market_value"] == "5100.00"
    assert position["unrealized_pnl"] == "100.00"
    assert position["unrealized_pnl_pct"] == "2.00"
    assert position["stop_price"] == "95.00"
    assert position["strategy"] == "trend"
    assert position["currency"] == "USD"


async def test_published_state_without_a_quote_leaves_values_empty(world: World) -> None:
    await world.engine.submit_entry(signal())
    world.prices.pop("AAPL")
    await world.engine.reconcile()
    stored = await world.store.account_state()
    assert stored is not None
    position = stored[1]["positions"][0]
    assert (position["last_price"], position["market_value"]) == (None, None)


async def test_published_state_for_an_unknown_holding(world: World) -> None:
    world.price("MSFT", "50")
    await world.sim.submit(OrderRequest("m", MSFT, Side.BUY, 1, D(50), D(45)))
    await world.engine.reconcile()
    stored = await world.store.account_state()
    assert stored is not None
    assert stored[1]["reconciled"] is False
    assert stored[1]["positions"][0]["currency"] is None


async def test_prices_are_rounded_to_ticks_without_adding_risk(world: World) -> None:
    result = await world.engine.submit_entry(
        signal(
            "ticks",
            limit_price=D("100.2079"),
            stop_price=D("94.6612"),
            take_profit_price=D("120.004"),
        )
    )
    entry = await world.store.known_order(result.client_order_id)
    stop = await world.store.known_order(f"{result.client_order_id}.stop")
    tp = await world.store.known_order(f"{result.client_order_id}.tp")
    assert entry.limit_price == D("100.20")  # never pay more than planned
    assert stop.stop_price == D("94.67")  # stop closer, never farther
    assert tp.limit_price == D("120.01")
    raised = await world.engine.raise_stop(result.client_order_id, D("96.509"))
    assert raised.outcome is Outcome.STOP_RAISED
    assert (await world.store.known_order(f"{result.client_order_id}.stop")).stop_price == D(
        "96.50"
    )


async def test_the_offensive_level_allows_a_larger_position(world: World) -> None:
    from jarvis.risk.profiles import RiskProfile

    big = signal("big", quantity=150, stop_price=D(99))  # 15 % of the capital
    assert Reason.POSITION_LIMIT in (await world.engine.submit_entry(big)).reasons
    await world.store.set_risk_profile(RiskProfile.OFFENSIVE, actor="adam", at=NOW)
    world.clock.now = NOW + timedelta(days=1)
    world.price("AAPL", "100")
    result = await world.engine.submit_entry(signal("big2", quantity=150, stop_price=D(99)))
    assert Reason.POSITION_LIMIT not in result.reasons
