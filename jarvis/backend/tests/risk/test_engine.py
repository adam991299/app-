from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from jarvis.config.settings import Risk
from jarvis.domain import AssetClass, Instrument, Position, Quote, Side
from jarvis.risk.breakers import BreakerStatus, TradingState
from jarvis.risk.engine import MarketSession, OrderProposal, PendingOrder, RiskEngine
from jarvis.risk.reasons import Reason
from jarvis.risk.sizing import size_position
from tests.factories import (
    NOW,
    RISK,
    buy,
    context,
    instrument,
    position,
    quote,
    sell,
    session,
)

ENGINE = RiskEngine(RISK)
D = Decimal


def reasons(order: OrderProposal, **ctx: Any) -> tuple[Reason, ...]:
    decision = ENGINE.check(order, context(**ctx))
    assert decision.approved == (decision.reasons == ())
    return decision.reasons


# -- a normal order passes ------------------------------------------------------------


def test_reasonable_buy_is_approved() -> None:
    assert reasons(buy()) == ()


def test_clock_must_be_timezone_aware() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        ENGINE.check(buy(), context(now=datetime(2026, 11, 16, 16)))  # noqa: DTZ001


# -- validity ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("order", "expected"),
    [
        (buy(quantity=0), (Reason.INVALID_QUANTITY,)),
        (buy(limit="0"), (Reason.INVALID_PRICE,)),
        (buy(cost="-1"), (Reason.INVALID_PRICE,)),
        (sell(quantity=-1, limit="-1"), (Reason.INVALID_QUANTITY, Reason.INVALID_PRICE)),
    ],
)
def test_invalid_orders(order: OrderProposal, expected: tuple[Reason, ...]) -> None:
    assert reasons(order) == expected


def test_stop_is_required_and_below_entry() -> None:
    assert reasons(buy(stop=None)) == (Reason.MISSING_STOP,)
    assert reasons(buy(stop="100")) == (Reason.INVALID_STOP,)
    assert reasons(buy(stop="0")) == (Reason.INVALID_STOP,)


def test_edge_must_clearly_exceed_costs() -> None:
    assert reasons(buy(edge=None)) == (Reason.MISSING_EDGE,)
    assert reasons(buy(edge="9.99", cost="5")) == (Reason.EDGE_TOO_SMALL,)
    assert reasons(buy(edge="10", cost="5")) == ()
    assert reasons(buy(edge="0", cost="0")) == (Reason.EDGE_TOO_SMALL,)


# -- trading state ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "state",
    [
        TradingState.NO_NEW_TRADES,
        TradingState.CLOSING_ONLY,
        TradingState.PAUSED,
        TradingState.KILL_SWITCH,
        TradingState.HALTED,
    ],
)
def test_blocked_states_stop_new_positions(state: TradingState) -> None:
    status = BreakerStatus(state, (Reason.PAUSED,), kill_switch_should_engage=False)
    assert reasons(buy(), breakers=status) == (Reason.PAUSED,)


@pytest.mark.parametrize(
    "state", [TradingState.NO_NEW_TRADES, TradingState.CLOSING_ONLY, TradingState.KILL_SWITCH]
)
def test_closing_is_allowed_when_new_trades_are_blocked(state: TradingState) -> None:
    status = BreakerStatus(state, (Reason.KILL_SWITCH_ENGAGED,), kill_switch_should_engage=False)
    held = {"AAPL": position(instrument(), 10)}
    assert reasons(sell(), breakers=status, positions=held) == ()


def test_halted_blocks_closing_too() -> None:
    status = BreakerStatus(TradingState.HALTED, (Reason.NOT_RECONCILED,), False)
    held = {"AAPL": position(instrument(), 10)}
    assert reasons(sell(), breakers=status, positions=held) == (Reason.NOT_RECONCILED,)


# -- long only --------------------------------------------------------------------------


def test_cannot_sell_what_is_not_held() -> None:
    assert reasons(sell()) == (Reason.SHORT_SELLING_NOT_ALLOWED,)
    held = {"AAPL": position(instrument(), 5)}
    assert reasons(sell(quantity=6), positions=held) == (Reason.SHORT_SELLING_NOT_ALLOWED,)
    assert reasons(sell(quantity=5), positions=held) == ()


def test_duplicate_close_signals_cannot_oversell() -> None:
    held = {"AAPL": position(instrument(), 10)}
    working = [PendingOrder(instrument(), Side.SELL, 10, D(100))]
    assert reasons(sell(), positions=held, pending=working) == (Reason.SHORT_SELLING_NOT_ALLOWED,)
    other = [PendingOrder(instrument("MSFT"), Side.SELL, 10, D(100))]
    assert reasons(sell(), positions=held, pending=other) == ()


# -- market data and timing ---------------------------------------------------------------


def test_missing_and_stale_quotes() -> None:
    assert reasons(buy(), quotes=[]) == (Reason.MISSING_QUOTE,)
    assert reasons(buy(), quotes=[quote(age_s=61)]) == (Reason.STALE_QUOTE,)
    assert reasons(buy(), quotes=[quote(age_s=60)]) == ()
    held = {"AAPL": position(instrument(), 10)}
    assert reasons(sell(), quotes=[], positions=held) == (Reason.MISSING_QUOTE,)


def test_fat_finger_price_deviation() -> None:
    assert reasons(buy(limit="103.01", stop="98")) == (Reason.PRICE_DEVIATION,)
    assert reasons(buy(limit="103", stop="98")) == ()
    held = {"AAPL": position(instrument(), 10)}
    assert reasons(sell(limit="96.9"), positions=held) == (Reason.PRICE_DEVIATION,)


def test_closed_market() -> None:
    closed = MarketSession(None, None)
    assert reasons(buy(), market=closed) == (Reason.MARKET_CLOSED,)
    after = session(NOW - timedelta(hours=7), NOW - timedelta(minutes=1))
    assert reasons(buy(), market=after) == (Reason.MARKET_CLOSED,)
    held = {"AAPL": position(instrument(), 10)}
    assert reasons(sell(), market=closed, positions=held) == (Reason.MARKET_CLOSED,)


@pytest.mark.parametrize(
    ("opened_ago", "closes_in", "blocked"),
    [
        (timedelta(minutes=9), timedelta(hours=6), True),
        (timedelta(minutes=10), timedelta(hours=6), False),
        (timedelta(hours=6), timedelta(minutes=10), False),
        (timedelta(hours=6), timedelta(minutes=9), True),
    ],
)
def test_no_new_positions_near_open_or_close(
    opened_ago: timedelta, closes_in: timedelta, blocked: bool
) -> None:
    market = session(NOW - opened_ago, NOW + closes_in)
    expected = (Reason.OUTSIDE_TRADING_WINDOW,) if blocked else ()
    assert reasons(buy(), market=market) == expected
    held = {"AAPL": position(instrument(), 10)}
    assert reasons(sell(), market=market, positions=held) == ()


def test_order_rate_limits() -> None:
    assert reasons(buy(), orders_last_minute=10) == (Reason.ORDER_RATE_MINUTE,)
    assert reasons(buy(), orders_today=50) == (Reason.ORDER_RATE_DAY,)
    assert reasons(buy(), orders_last_minute=9, orders_today=49) == ()


def test_closing_is_not_rate_limited() -> None:
    held = {"AAPL": position(instrument(), 10)}
    assert reasons(sell(), positions=held, orders_last_minute=99, orders_today=999) == ()


def test_future_dated_quote_is_rejected() -> None:
    assert reasons(buy(), quotes=[quote(age_s=-2)]) == (Reason.FUTURE_QUOTE,)
    assert reasons(buy(), quotes=[quote(age_s=-1)]) == ()


def test_sell_may_not_touch_shares_covered_by_a_broker_stop() -> None:
    held = {"AAPL": position(instrument(), 10)}
    assert reasons(sell(), positions=held, protected={"AAPL": 10}) == (Reason.COVERED_BY_STOP,)
    assert reasons(sell(quantity=4), positions=held, protected={"AAPL": 6}) == ()
    assert reasons(sell(quantity=5), positions=held, protected={"AAPL": 6}) == (
        Reason.COVERED_BY_STOP,
    )


def test_sector_names_are_compared_normalised() -> None:
    held = {f"S{i}": position(instrument(f"S{i}", sector="Technology"), 100) for i in range(2)}
    quotes = [quote("S0"), quote("S1"), quote()]
    order = buy(instrument(sector="technology "), quantity=51, stop="99.9")
    assert reasons(order, positions=held, quotes=quotes) == (Reason.SECTOR_LIMIT,)


def test_gap_loss_counts_a_stop_wider_than_the_gap() -> None:
    # stop at 40 (60 % away) is wider than the 25 % gap scenario: 60 per share x 51 > 3 000
    assert Reason.GAP_LOSS_LIMIT in reasons(buy(quantity=51, limit="100", stop="40"))


# -- sizing and portfolio limits -----------------------------------------------------------


def test_trade_risk_limit() -> None:
    # 100 shares x 7.51 to the stop = 751 > 750 (0.75 % of 100 000)
    assert reasons(buy(quantity=100, stop="92.49")) == (Reason.TRADE_RISK_LIMIT,)
    assert reasons(buy(quantity=100, stop="92.5")) == ()


def test_position_limit_includes_existing_and_pending() -> None:
    assert reasons(buy(quantity=101, stop="99.9")) == (Reason.POSITION_LIMIT,)
    held = {"AAPL": position(instrument(), 60)}
    assert reasons(buy(quantity=41, stop="99.9"), positions=held) == (Reason.POSITION_LIMIT,)
    working = [PendingOrder(instrument(), Side.BUY, 60, D(100))]
    assert reasons(buy(quantity=41, stop="99.9"), pending=working) == (Reason.POSITION_LIMIT,)
    assert reasons(buy(quantity=40, stop="99.9"), pending=working) == ()


def test_duplicate_buy_signals_cannot_exceed_limits() -> None:
    order = buy(quantity=60, stop="99.9")
    assert reasons(order) == ()
    working = [PendingOrder(instrument(), Side.BUY, 60, D(100))]
    assert reasons(order, pending=working) == (Reason.POSITION_LIMIT,)


def test_crypto_and_small_cap_caps() -> None:
    coin = instrument("BTC", asset_class=AssetClass.CRYPTO, sector=None)
    assert reasons(buy(coin, quantity=51, stop="99.9"), quotes=[quote("BTC")]) == (
        Reason.POSITION_LIMIT,
    )
    small = instrument("TINY", small_cap=True)
    assert reasons(buy(small, quantity=51, stop="99.9"), quotes=[quote("TINY")]) == (
        Reason.POSITION_LIMIT,
    )


def test_gap_loss_limit() -> None:
    risk = Risk.model_validate({"gap": {"single_stock_gap_pct": 50}})
    decision = RiskEngine(risk).check(buy(quantity=61, stop="99.9"), context())
    assert decision.reasons == (Reason.GAP_LOSS_LIMIT,)


def _holdings(n: int, sector: str = "technology") -> tuple[dict[str, Position], list[Quote]]:
    held = {f"S{i}": position(instrument(f"S{i}", sector=sector), 100) for i in range(n)}
    return held, [quote(f"S{i}") for i in range(n)]


def test_sector_limit() -> None:
    held, quotes = _holdings(2)  # 20 000 in technology already
    assert reasons(buy(quantity=51, stop="99.9"), positions=held, quotes=[*quotes, quote()]) == (
        Reason.SECTOR_LIMIT,
    )
    assert reasons(buy(quantity=50, stop="99.9"), positions=held, quotes=[*quotes, quote()]) == ()
    other = buy(instrument("XOM", sector="energy"), quantity=100, stop="99.9")
    assert reasons(other, positions=held, quotes=[*quotes, quote("XOM")]) == ()


def test_unknown_sector_is_rejected_for_stocks() -> None:
    nameless = instrument(sector=None)
    assert reasons(buy(nameless)) == (Reason.UNKNOWN_SECTOR,)


def test_crypto_total_limit() -> None:
    coins = {
        f"C{i}": position(instrument(f"C{i}", asset_class=AssetClass.CRYPTO, sector=None), 50)
        for i in range(3)
    }
    quotes = [quote(f"C{i}") for i in range(3)] + [quote("ETH")]
    eth = buy(instrument("ETH", asset_class=AssetClass.CRYPTO, sector=None), 1, stop="99.9")
    assert reasons(eth, positions=coins, quotes=quotes) == (Reason.CRYPTO_LIMIT,)


def test_commodities_total_limit() -> None:
    def gold(i: int) -> Instrument:
        return instrument(f"G{i}", asset_class=AssetClass.COMMODITY, sector=None)

    held = {f"G{i}": position(gold(i), 100) for i in range(2)}  # 20 000
    quotes = [quote(f"G{i}") for i in range(3)]
    assert reasons(buy(gold(2), 1, stop="99.9"), positions=held, quotes=quotes) == (
        Reason.COMMODITIES_LIMIT,
    )


def test_gross_exposure_and_cash_reserve() -> None:
    held: dict[str, Position] = {}
    quotes: list[Quote] = []
    for i, sector in enumerate(["a", "b", "c", "d", "e", "f", "g", "h", "i"]):
        held[f"S{i}"] = position(instrument(f"S{i}", sector=sector), 100)
        quotes.append(quote(f"S{i}"))
    order = buy(instrument("NEW", sector="z"), quantity=100, stop="99.9")
    # 90 000 held + 10 000 new + 5 cost = 100 005 of 100 000 equity, cash 10 000
    got = reasons(order, positions=held, quotes=[*quotes, quote("NEW")], cash="10000")
    assert got == (Reason.CASH_RESERVE,)
    leveraged = reasons(
        order, positions=held, quotes=[*quotes, quote("NEW")], cash="100000", equity="99000"
    )
    assert Reason.GROSS_EXPOSURE_LIMIT in leveraged


def test_cash_reserve_counts_pending_buys() -> None:
    working = [PendingOrder(instrument("MSFT"), Side.BUY, 100, D(100))]
    got = reasons(
        buy(quantity=50, stop="99.9"),
        cash="15000",
        pending=working,
        quotes=[quote(), quote("MSFT")],
    )
    assert got == (Reason.CASH_RESERVE,)


def test_pending_sells_do_not_count_as_exposure() -> None:
    held = {"AAPL": position(instrument(), 50)}
    working = [PendingOrder(instrument(), Side.SELL, 50, D(100))]
    assert reasons(buy(quantity=50, stop="99.9"), positions=held, pending=working) == ()


def test_missing_quote_for_holdings_or_pending_fails_closed() -> None:
    held = {"MSFT": position(instrument("MSFT"), 10)}
    assert reasons(buy(), positions=held) == (Reason.MISSING_QUOTE,)
    working = [PendingOrder(instrument("MSFT"), Side.BUY, 10, D(100))]
    assert reasons(buy(), pending=working) == (Reason.MISSING_QUOTE,)


def test_no_equity() -> None:
    assert reasons(buy(), equity="0", cash="1000") == (Reason.NO_EQUITY,)


def test_max_open_positions() -> None:
    risk = Risk.model_validate(
        {"concurrency": {"max_open_positions": 2, "max_concurrent_daytrades": 1}}
    )
    held = {f"S{i}": position(instrument(f"S{i}", sector=f"s{i}"), 1) for i in range(2)}
    quotes = [quote("S0"), quote("S1"), quote()]
    decision = RiskEngine(risk).check(buy(), context(positions=held, quotes=quotes))
    assert decision.reasons == (Reason.MAX_OPEN_POSITIONS,)
    adding = RiskEngine(risk).check(
        buy(instrument("S0", sector="s0")), context(positions=held, quotes=quotes)
    )
    assert adding.approved


def test_fx_is_applied_to_values() -> None:
    # 10 SEK per USD: 11 shares x 100 USD = 11 000 SEK > 10 % of 100 000 SEK
    assert reasons(buy(quantity=11, stop="99.9"), quotes=[quote(fx="10")]) == (
        Reason.POSITION_LIMIT,
    )


def test_all_failing_checks_are_reported() -> None:
    got = reasons(buy(quantity=1000, stop=None, edge=None), orders_today=99)
    assert {Reason.ORDER_RATE_DAY, Reason.MISSING_STOP, Reason.MISSING_EDGE} <= set(got)
    assert Reason.POSITION_LIMIT in got
    assert len(got) == len(set(got))


# -- properties ---------------------------------------------------------------------------


@settings(max_examples=400)
@given(
    entry=st.decimals(min_value=D(1), max_value=D(1000), places=2),
    stop_fraction=st.decimals(min_value=D("0.30"), max_value=D("0.995"), places=3),
    fx=st.decimals(min_value=D("0.1"), max_value=D(15), places=2),
    cash=st.decimals(min_value=D(5000), max_value=D(10**7), places=0),
    held_value=st.decimals(min_value=D(0), max_value=D(10**6), places=0),
    held_fx=st.decimals(min_value=D("0.1"), max_value=D(15), places=2),
    asset_class=st.sampled_from([AssetClass.EQUITY, AssetClass.ETF, AssetClass.CRYPTO]),
    small_cap=st.booleans(),
)
def test_sizing_is_exactly_the_largest_approved_quantity(
    entry: Decimal,
    stop_fraction: Decimal,
    fx: Decimal,
    cash: Decimal,
    held_value: Decimal,
    held_fx: Decimal,
    asset_class: AssetClass,
    small_cap: bool,
) -> None:
    """The sized quantity is approved and one more share is rejected, with an unrelated
    holding in another currency and sector on the books."""
    stop = (entry * stop_fraction).quantize(D("0.01"))
    if not 0 < stop < entry:
        return
    other_qty = int(held_value / 100) if held_value >= 100 else 0
    held = (
        {"OTHER": position(instrument("OTHER", sector="utilities"), other_qty)} if other_qty else {}
    )
    equity = cash + other_qty * 100 * held_fx
    sector = None if asset_class is AssetClass.CRYPTO else "unique"
    inst = instrument("NEW", asset_class=asset_class, sector=sector, small_cap=small_cap)
    cost = D(1)
    sized = size_position(
        instrument=inst,
        equity=equity,
        free_cash=cash - equity * D("0.05") - cost,
        entry=entry,
        stop=stop,
        fx_to_base=fx,
        risk=RISK,
    )
    quotes = [quote("NEW", last=str(entry), fx=str(fx)), quote("OTHER", fx=str(held_fx))]
    ctx = context(equity=str(equity), cash=str(cash), positions=held, quotes=quotes)
    bigger = ENGINE.check(
        buy(inst, sized.quantity + 1, str(entry), str(stop), edge="1e9", cost="1"), ctx
    )
    assert not bigger.approved
    if sized.quantity > 0:
        exact = ENGINE.check(
            buy(inst, sized.quantity, str(entry), str(stop), edge="1e9", cost="1"), ctx
        )
        assert exact.approved, exact.reasons
