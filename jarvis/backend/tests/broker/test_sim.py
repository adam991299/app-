from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest

from jarvis.broker import (
    BrokerAdapter,
    BrokerError,
    BrokerUnavailableError,
    DuplicateOrderIdError,
    OrderRequest,
    OrderStatus,
)
from jarvis.broker.sim import SimBroker
from jarvis.domain import Side
from tests.factories import NOW, instrument

D = Decimal
AAPL = instrument()


def run[T](coro: Coroutine[Any, Any, T]) -> T:
    return asyncio.run(coro)


def broker(cash: str = "100000", **kwargs: Any) -> SimBroker:
    sim = SimBroker(cash=D(cash), clock=lambda: NOW, minimum_commission=D(1), **kwargs)
    run(sim.connect())
    sim.set_price("AAPL", D(100))
    return sim


def bracket(
    cid: str = "o1", qty: int = 10, limit: str = "100", stop: str = "95", tp: str | None = None
) -> OrderRequest:
    return OrderRequest(cid, AAPL, Side.BUY, qty, D(limit), D(stop), None if tp is None else D(tp))


def exit_order(cid: str = "x1", qty: int = 10, limit: str = "100") -> OrderRequest:
    return OrderRequest(cid, AAPL, Side.SELL, qty, D(limit))


def status(sim: SimBroker, cid: str) -> OrderStatus:
    found = run(sim.order(cid))
    assert found is not None
    return found.status


def held(sim: SimBroker) -> int:
    positions = run(sim.positions())
    return positions[0].quantity if positions else 0


def test_satisfies_the_adapter_protocol() -> None:
    adapter: BrokerAdapter = broker()
    assert adapter.is_connected()


# -- request validation ---------------------------------------------------------------


@pytest.mark.parametrize(
    "kwargs",
    [
        {"client_order_id": ""},
        {"quantity": 0},
        {"limit_price": D(0)},
        {"side": Side.SELL, "stop_price": D(95)},
        {"stop_price": D(100)},
        {"stop_price": D(0)},
        {"take_profit_price": D(110), "stop_price": None},
        {"take_profit_price": D(100)},
    ],
)
def test_invalid_requests(kwargs: dict[str, Any]) -> None:
    base: dict[str, Any] = {
        "client_order_id": "o1",
        "instrument": AAPL,
        "side": Side.BUY,
        "quantity": 10,
        "limit_price": D(100),
        "stop_price": D(95),
    }
    with pytest.raises(ValueError, match=r"required|positive|long|stop|take-profit"):
        OrderRequest(**(base | kwargs))


def test_status_helpers() -> None:
    assert OrderStatus.SUBMITTED.is_working
    assert OrderStatus.PARTIALLY_FILLED.is_working
    assert not OrderStatus.NEW.is_working
    assert {s for s in OrderStatus if s.is_terminal} == {
        OrderStatus.FILLED,
        OrderStatus.CANCELLED,
        OrderStatus.REJECTED,
        OrderStatus.EXPIRED,
    }


# -- connection --------------------------------------------------------------------------


def test_calls_fail_when_disconnected() -> None:
    sim = broker()
    run(sim.disconnect())
    assert not sim.is_connected()
    for call in (
        sim.account(),
        sim.positions(),
        sim.open_orders(),
        sim.order("x"),
        sim.fills(NOW),
        sim.submit(bracket()),
        sim.cancel("x"),
    ):
        with pytest.raises(BrokerUnavailableError):
            run(call)


def test_offline_broker_refuses_connection_until_online() -> None:
    sim = broker()
    sim.go_offline()
    with pytest.raises(BrokerUnavailableError, match="offline"):
        run(sim.connect())
    sim.go_online()
    run(sim.connect())
    assert sim.is_connected()


def test_injected_failure_happens_once() -> None:
    sim = broker()
    sim.fail_next_call(BrokerError("timeout"))
    with pytest.raises(BrokerError, match="timeout"):
        run(sim.account())
    assert run(sim.account()).cash == D(100000)


# -- entries and brackets -------------------------------------------------------------------


def test_marketable_bracket_fills_and_activates_stop() -> None:
    sim = broker()
    order = run(sim.submit(bracket(limit="100.5")))
    assert order.status is OrderStatus.FILLED
    assert order.average_fill_price == D(100)
    assert held(sim) == 10
    stop = run(sim.order("o1.stop"))
    assert stop is not None
    assert stop.status is OrderStatus.SUBMITTED
    assert stop.parent_id == "o1"
    account = run(sim.account())
    assert account.cash == D(100000) - D(1000) - D(1)
    assert account.net_liquidation == D(100000) - D(1)


def test_resting_limit_waits_for_price() -> None:
    sim = broker()
    run(sim.submit(bracket(limit="99")))
    assert status(sim, "o1") is OrderStatus.SUBMITTED
    sim.set_price("AAPL", D("98.5"))
    assert status(sim, "o1") is OrderStatus.FILLED
    assert run(sim.fills(NOW))[0].price == D("98.5")


def test_stop_does_not_fire_before_entry_fills() -> None:
    sim = broker()
    run(sim.submit(bracket(limit="90", stop="85")))
    assert status(sim, "o1.stop") is OrderStatus.SUBMITTED
    sim.set_price("AAPL", D(84))  # fills the entry; stop now active and also triggered
    assert status(sim, "o1") is OrderStatus.FILLED
    assert status(sim, "o1.stop") is OrderStatus.FILLED
    assert held(sim) == 0


def test_gap_through_stop_fills_at_gap_price() -> None:
    sim = broker()
    run(sim.submit(bracket()))
    sim.set_price("AAPL", D(80))
    stop = run(sim.order("o1.stop"))
    assert stop is not None
    assert stop.status is OrderStatus.FILLED
    assert stop.average_fill_price == D(80)
    assert held(sim) == 0
    assert run(sim.open_orders()) == ()


def test_take_profit_cancels_stop() -> None:
    sim = broker()
    run(sim.submit(bracket(tp="110")))
    sim.set_price("AAPL", D(111))
    assert status(sim, "o1.tp") is OrderStatus.FILLED
    assert status(sim, "o1.stop") is OrderStatus.CANCELLED
    assert held(sim) == 0


def test_stop_cancels_take_profit() -> None:
    sim = broker()
    run(sim.submit(bracket(tp="110")))
    sim.set_price("AAPL", D(90))
    assert status(sim, "o1.stop") is OrderStatus.FILLED
    assert status(sim, "o1.tp") is OrderStatus.CANCELLED


def test_stops_keep_working_while_jarvis_is_offline() -> None:
    sim = broker()
    run(sim.submit(bracket()))
    sim.go_offline()
    sim.set_price("AAPL", D(94))  # the market moves while the gateway is down
    sim.go_online()
    run(sim.connect())
    assert held(sim) == 0
    assert status(sim, "o1.stop") is OrderStatus.FILLED


# -- partial fills ---------------------------------------------------------------------------


def test_partial_fills_are_always_fully_protected() -> None:
    sim = broker(max_fill_per_price=4)
    first = run(sim.submit(bracket(limit="100")))
    assert first.status is OrderStatus.PARTIALLY_FILLED
    assert first.filled_quantity == 4
    sim.set_price("AAPL", D("99.9"))
    assert held(sim) == 8
    run(sim.cancel("o1"))  # the rest of the entry is no longer wanted
    sim.set_price("AAPL", D(94))  # stop sells only what was bought, 4 at a time
    assert held(sim) == 4
    sim.set_price("AAPL", D(93))
    assert held(sim) == 0
    stop = run(sim.order("o1.stop"))
    assert stop is not None
    assert stop.filled_quantity == 8


def test_cancelling_a_partly_filled_entry_shrinks_its_stop() -> None:
    sim = broker(max_fill_per_price=3)
    run(sim.submit(bracket(tp="110")))
    run(sim.cancel("o1"))
    stop = run(sim.order("o1.stop"))
    assert stop is not None
    assert (stop.quantity, stop.status) == (3, OrderStatus.SUBMITTED)
    sim.set_price("AAPL", D(90))
    assert status(sim, "o1.stop") is OrderStatus.FILLED
    assert status(sim, "o1.tp") is OrderStatus.CANCELLED
    assert held(sim) == 0


def test_sibling_that_sold_part_is_marked_filled_when_bracket_closes() -> None:
    sim = broker(max_fill_per_price=5)
    run(sim.submit(bracket(qty=10, tp="110")))
    sim.set_price("AAPL", D("99.9"))  # entry fully filled (5 + 5)
    sim.set_price("AAPL", D(111))  # target sells 5
    sim.set_price("AAPL", D(90))  # stop sells the last 5
    tp, stop = run(sim.order("o1.tp")), run(sim.order("o1.stop"))
    assert tp is not None
    assert stop is not None
    assert (tp.status, tp.quantity, tp.filled_quantity) == (OrderStatus.FILLED, 5, 5)
    assert (stop.status, stop.filled_quantity) == (OrderStatus.FILLED, 5)
    assert held(sim) == 0


# -- cancel, expire ----------------------------------------------------------------------------


def test_cancel_unfilled_entry_cancels_children() -> None:
    sim = broker()
    run(sim.submit(bracket(limit="90", stop="85", tp="120")))
    cancelled = run(sim.cancel("o1"))
    assert cancelled.status is OrderStatus.CANCELLED
    assert status(sim, "o1.stop") is OrderStatus.CANCELLED
    assert status(sim, "o1.tp") is OrderStatus.CANCELLED
    sim.set_price("AAPL", D(80))
    assert held(sim) == 0
    assert run(sim.cancel("o1")).status is OrderStatus.CANCELLED  # idempotent


def test_cancel_unknown_order() -> None:
    with pytest.raises(BrokerError, match="unknown order"):
        run(broker().cancel("nope"))


def test_cancelling_the_stop_leaves_position() -> None:
    sim = broker()
    run(sim.submit(bracket()))
    run(sim.cancel("o1.stop"))
    sim.set_price("AAPL", D(50))
    assert held(sim) == 10


def test_day_orders_expire_but_stops_stay() -> None:
    sim = broker()
    run(sim.submit(bracket(cid="filled")))
    run(sim.submit(bracket(cid="resting", limit="90", stop="85")))
    run(sim.submit(bracket(cid="plain", qty=5)))
    run(sim.cancel("plain.stop"))
    run(sim.submit(exit_order(limit="120", qty=5)))
    sim.expire_day_orders()
    assert status(sim, "resting") is OrderStatus.EXPIRED
    assert status(sim, "resting.stop") is OrderStatus.CANCELLED
    assert status(sim, "x1") is OrderStatus.EXPIRED
    assert status(sim, "filled.stop") is OrderStatus.SUBMITTED


# -- idempotency ------------------------------------------------------------------------------


def test_resubmitting_same_order_does_not_duplicate() -> None:
    sim = broker()
    first = run(sim.submit(bracket()))
    again = run(sim.submit(bracket()))
    assert again == first
    assert held(sim) == 10
    assert len(run(sim.fills(NOW))) == 1


def test_reused_id_with_different_order_is_refused() -> None:
    sim = broker()
    run(sim.submit(bracket()))
    with pytest.raises(DuplicateOrderIdError):
        run(sim.submit(bracket(qty=11)))
    with pytest.raises(DuplicateOrderIdError):
        run(sim.submit(exit_order(cid="o1.stop")))


# -- cash account rules -----------------------------------------------------------------------


def test_no_buying_beyond_cash() -> None:
    sim = broker(cash="1000")
    rejected = run(sim.submit(bracket(qty=10)))  # 1 000 + commission > 1 000
    assert rejected.status is OrderStatus.REJECTED
    assert rejected.reject_reason is not None
    assert "cash" in rejected.reject_reason
    assert run(sim.order("o1.stop")) is None
    assert run(sim.submit(bracket(cid="o2", qty=9))).status is OrderStatus.FILLED


def test_working_buys_reserve_cash() -> None:
    sim = broker(cash="2000")
    run(sim.submit(bracket(cid="a", limit="99", stop="90")))  # rests, reserves 990
    assert run(sim.submit(bracket(cid="b", qty=11, limit="99", stop="90"))).status is (
        OrderStatus.REJECTED
    )


def test_no_short_selling() -> None:
    sim = broker()
    assert run(sim.submit(exit_order(cid="x0"))).status is OrderStatus.REJECTED
    run(sim.submit(bracket(cid="buy")))
    run(sim.cancel("buy.stop"))
    run(sim.submit(exit_order(cid="x1", qty=6, limit="101")))
    assert run(sim.submit(exit_order(cid="x2", qty=5, limit="101"))).status is (
        OrderStatus.REJECTED
    )


def test_exit_sells_at_or_above_limit() -> None:
    sim = broker()
    run(sim.submit(bracket(cid="buy")))
    run(sim.cancel("buy.stop"))
    run(sim.submit(exit_order(limit="105")))
    assert held(sim) == 10
    sim.set_price("AAPL", D(106))
    assert held(sim) == 0
    account = run(sim.account())
    assert account.cash == D(100000) - D(1001) + D(1060) - D(1)


def test_exit_overlapping_a_working_stop_is_rejected() -> None:
    sim = broker()
    run(sim.submit(bracket(cid="b1")))
    overlapping = run(sim.submit(exit_order(limit="100")))
    assert overlapping.status is OrderStatus.REJECTED
    assert overlapping.reject_reason is not None
    assert "cancel the stop" in overlapping.reject_reason


def test_old_stop_cannot_sell_shares_from_a_later_buy() -> None:
    """Reviewer scenario: exit, re-buy, price drop. The old stop must not fire."""
    sim = broker()
    run(sim.submit(bracket(cid="b1")))
    run(sim.cancel("b1.stop"))
    run(sim.submit(exit_order(limit="100")))
    run(sim.submit(bracket(cid="b2", stop="90")))
    sim.set_price("AAPL", D(94))
    assert held(sim) == 10
    assert status(sim, "b1.stop") is OrderStatus.CANCELLED


def test_two_brackets_on_one_symbol_each_protect_their_own_shares() -> None:
    sim = broker()
    run(sim.submit(bracket(cid="a", stop="95")))
    run(sim.submit(bracket(cid="b", qty=5, stop="90")))
    sim.set_price("AAPL", D(94))
    assert held(sim) == 5
    sim.set_price("AAPL", D(89))
    assert held(sim) == 0


def test_cash_reservation_includes_commission() -> None:
    sim = broker(cash="1000")
    sim.set_price("AAPL", D(20))
    run(sim.submit(bracket(cid="a", qty=99, limit="10", stop="9")))  # rests: 990 + 1
    late = run(sim.submit(bracket(cid="b", qty=1, limit="9", stop="8")))  # needs 9 + 1 > 9 left
    assert late.status is OrderStatus.REJECTED
    sim.set_price("AAPL", D(9))
    assert run(sim.account()).cash >= 0


def test_partial_exit_keeps_average_cost_and_positions_list() -> None:
    sim = broker()
    run(sim.submit(bracket(cid="buy")))
    run(sim.cancel("buy.stop"))
    run(sim.submit(exit_order(qty=4, limit="100")))
    positions = run(sim.positions())
    assert [(p.symbol, p.quantity, p.average_cost) for p in positions] == [("AAPL", 6, D(100))]


def test_fills_since_filters_by_time() -> None:
    sim = broker()
    run(sim.submit(bracket()))
    sim.set_price("AAPL", D(90))
    fills = run(sim.fills(NOW))
    assert [f.fill_id for f in fills] == ["sim-1", "sim-2"]
    assert run(sim.fills(NOW + timedelta(seconds=1))) == ()


def test_price_must_be_positive_and_unknown_symbols_wait() -> None:
    sim = broker()
    with pytest.raises(ValueError, match="positive"):
        sim.set_price("AAPL", D(0))
    msft = instrument("MSFT")
    order = run(sim.submit(OrderRequest("m", msft, Side.BUY, 1, D(10), D(9))))
    assert order.status is OrderStatus.SUBMITTED  # no price yet, nothing fills
    assert run(sim.account()).net_liquidation == D(100000)


def test_account_values_positions_at_cost_without_price() -> None:
    sim = SimBroker(cash=D(1000), clock=lambda: NOW)
    run(sim.connect())
    sim.set_price("AAPL", D(10))
    run(sim.submit(bracket(qty=5, limit="10", stop="9")))
    assert run(sim.account()).net_liquidation == D(1000) - D(1)


def test_target_waits_when_it_has_sold_everything_bought_so_far() -> None:
    sim = broker(max_fill_per_price=4)
    run(sim.submit(bracket(tp="110")))  # entry fills 4 of 10, keeps working
    sim.set_price("AAPL", D(111))  # target sells those 4
    sim.set_price("AAPL", D(112))  # nothing more to sell yet: no empty fill
    tp = run(sim.order("o1.tp"))
    assert tp is not None
    assert tp.filled_quantity == 4
    assert held(sim) == 0
    assert len(run(sim.fills(NOW))) == 2
    assert status(sim, "o1") is OrderStatus.PARTIALLY_FILLED


def test_orders_report_their_price_levels() -> None:
    sim = broker()
    run(sim.submit(bracket(limit="99", tp="110")))
    entry, stop, tp = (run(sim.order(c)) for c in ("o1", "o1.stop", "o1.tp"))
    assert entry is not None
    assert stop is not None
    assert tp is not None
    assert (entry.limit_price, entry.stop_price) == (D(99), None)
    assert (stop.limit_price, stop.stop_price) == (None, D(95))
    assert (tp.limit_price, tp.stop_price) == (D(110), None)


def test_raising_a_stop_moves_the_exit() -> None:
    sim = broker()
    run(sim.submit(bracket()))
    moved = run(sim.modify_stop("o1.stop", D(98)))
    assert moved.stop_price == D(98)
    sim.set_price("AAPL", D("97.5"))
    assert held(sim) == 0
    stop = run(sim.order("o1.stop"))
    assert stop is not None
    assert stop.average_fill_price == D("97.5")


def test_moving_a_stop_through_the_price_triggers_it() -> None:
    sim = broker()
    run(sim.submit(bracket()))
    run(sim.modify_stop("o1.stop", D(101)))
    assert held(sim) == 0


@pytest.mark.parametrize(
    ("cid", "price", "match"),
    [
        ("o1", "98", "no protective stop"),
        ("nope", "98", "no protective stop"),
        ("o1.stop", "0", "positive"),
    ],
)
def test_modify_stop_errors(cid: str, price: str, match: str) -> None:
    sim = broker()
    run(sim.submit(bracket()))
    with pytest.raises(BrokerError, match=match):
        run(sim.modify_stop(cid, D(price)))


def test_finished_stop_cannot_be_moved() -> None:
    sim = broker()
    run(sim.submit(bracket()))
    sim.set_price("AAPL", D(90))
    with pytest.raises(BrokerError, match="no longer working"):
        run(sim.modify_stop("o1.stop", D(80)))
