from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from jarvis.broker.models import Fill, OrderStatus
from jarvis.domain import Side
from jarvis.store.db import DatabaseConfigError, database_url_from_env
from jarvis.store.repo import NewOrder, Store
from tests.conftest import ALEMBIC_INI, migrate

D = Decimal
# Monday 16 Nov 2026, 16:00 UTC = 17:00 in Stockholm
NOW = datetime(2026, 11, 16, 16, tzinfo=UTC)


async def test_starts_in_paper_with_nothing_engaged(store: Store) -> None:
    controls = await store.controls()
    assert controls.trading_mode == "paper"
    assert not controls.paused
    assert not controls.kill_switch_engaged
    assert controls.peak_reset_at is None


async def test_live_mode_cannot_be_written_as_garbage(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        with pytest.raises(IntegrityError):
            await conn.execute(text("UPDATE controls SET trading_mode = 'yolo'"))


async def test_only_one_controls_row(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        with pytest.raises(IntegrityError):
            await conn.execute(
                text(
                    "INSERT INTO controls (id, trading_mode, paused, kill_switch_engaged, "
                    "updated_at) VALUES (2, 'paper', false, false, now())"
                )
            )


async def test_pause_and_resume_are_audited(store: Store) -> None:
    await store.set_paused(True, actor="adam", at=NOW)
    assert (await store.controls()).paused
    await store.set_paused(False, actor="adam", at=NOW)
    assert not (await store.controls()).paused
    assert await store.audit_entries() == [("adam", "resume", {}), ("adam", "pause", {})]


async def test_kill_switch_engage_once_and_reset_rebases_peak(store: Store) -> None:
    await store.engage_kill_switch("drawdown", actor="jarvis", at=NOW)
    await store.engage_kill_switch("drawdown again", actor="jarvis", at=NOW)
    controls = await store.controls()
    assert controls.kill_switch_engaged
    assert controls.kill_switch_reason == "drawdown"
    await store.reset_kill_switch(actor="adam", at=NOW + timedelta(hours=1))
    controls = await store.controls()
    assert not controls.kill_switch_engaged
    assert controls.kill_switch_reason is None
    assert controls.peak_reset_at == NOW + timedelta(hours=1)
    assert [a for _, a, _ in await store.audit_entries()] == [
        "kill_switch_reset",
        "kill_switch_engaged",
    ]


async def test_free_audit_entries(store: Store) -> None:
    await store.audit(actor="system", action="login", at=NOW, details={"ip": "tailnet"})
    await store.audit(actor="adam", action="check_in", at=NOW)
    assert await store.audit_entries(limit=1) == [("adam", "check_in", {})]


# -- equity marks ------------------------------------------------------------------------


async def snap(store: Store, at: datetime, value: str) -> None:
    await store.record_equity(at=at, net_liquidation=D(value), cash=D(value))


async def test_no_marks_before_first_snapshot(store: Store) -> None:
    assert await store.equity_marks(NOW) is None


async def test_marks_from_snapshots(store: Store) -> None:
    await snap(store, NOW - timedelta(days=7), "110")  # previous week: the peak
    await snap(store, NOW - timedelta(days=3), "105")  # Friday close, before this week
    await snap(store, NOW - timedelta(hours=10), "103")  # Monday 07:00 Stockholm
    await snap(store, NOW - timedelta(hours=2), "101")  # today's low
    await snap(store, NOW, "102")
    await snap(store, NOW + timedelta(hours=1), "50")  # future rows are ignored
    marks = await store.equity_marks(NOW)
    assert marks is not None
    assert marks.current == D(102)
    assert marks.day_start == D(105)  # last value before today began
    assert marks.day_low == D(101)
    assert marks.week_start == D(105)
    assert marks.week_low == D(101)
    assert marks.peak == D(110)


async def test_first_day_uses_first_snapshot_as_reference(store: Store) -> None:
    await snap(store, NOW - timedelta(hours=3), "100")
    await snap(store, NOW, "99")
    marks = await store.equity_marks(NOW)
    assert marks is not None
    assert (marks.day_start, marks.day_low, marks.week_start, marks.peak) == (
        D(100),
        D(99),
        D(100),
        D(100),
    )


async def test_peak_counts_only_since_kill_switch_reset(store: Store) -> None:
    await snap(store, NOW - timedelta(days=2), "120")
    await store.reset_kill_switch(actor="adam", at=NOW - timedelta(hours=1))
    await snap(store, NOW, "100")
    marks = await store.equity_marks(NOW)
    assert marks is not None
    assert marks.peak == D(100)


# -- risk decisions, orders and fills ---------------------------------------------------------


async def test_risk_decisions_are_logged(store: Store) -> None:
    for approved, reasons in ((False, ["stale_quote"]), (True, [])):
        await store.record_risk_decision(
            at=NOW,
            client_order_id="trend-1",
            symbol="AAPL",
            side="buy",
            quantity=10,
            approved=approved,
            reasons=reasons,
            trading_state="active",
        )
    assert await store.risk_decisions("trend-1") == [(False, ["stale_quote"]), (True, [])]


def entry(cid: str = "trend-1", **kw: object) -> NewOrder:
    base: dict[str, object] = {
        "client_order_id": cid,
        "kind": "entry",
        "symbol": "AAPL",
        "side": "buy",
        "quantity": 10,
        "limit_price": D("100.5"),
        "stop_price": D(95),
        "strategy": "trend",
        "explanation_sv": "Kursen bröt över 50-dagars högsta.",
        "signal": {"breakout": "100.2"},
    }
    return NewOrder(**(base | kw))  # type: ignore[arg-type]


async def test_order_is_journaled_once(store: Store) -> None:
    assert await store.add_order(entry(), at=NOW)
    assert not await store.add_order(entry(quantity=99), at=NOW)  # restart replay
    stored = await store.order("trend-1")
    assert stored is not None
    assert (stored.status, stored.quantity, stored.filled_quantity) == (OrderStatus.NEW, 10, 0)
    assert await store.order("missing") is None


async def test_order_updates_and_open_orders(store: Store) -> None:
    await store.add_order(entry(), at=NOW)
    await store.add_order(
        entry("trend-1.stop", kind="stop", side="sell", parent_id="trend-1", limit_price=None),
        at=NOW,
    )
    await store.update_order(
        "trend-1",
        at=NOW,
        status=OrderStatus.FILLED,
        filled_quantity=10,
        average_fill_price=D("100.25"),
    )
    await store.update_order(
        "trend-1.stop",
        at=NOW,
        status=OrderStatus.SUBMITTED,
        filled_quantity=0,
        average_fill_price=None,
        quantity=10,
    )
    open_ids = [o.client_order_id for o in await store.open_orders()]
    assert open_ids == ["trend-1.stop"]
    filled = await store.order("trend-1")
    assert filled is not None
    assert filled.average_fill_price == D("100.25")


async def test_rejection_reason_is_kept(store: Store, engine: AsyncEngine) -> None:
    await store.add_order(entry(), at=NOW)
    await store.update_order(
        "trend-1",
        at=NOW,
        status=OrderStatus.REJECTED,
        filled_quantity=0,
        average_fill_price=None,
        reject_reason="insufficient cash",
    )
    async with engine.connect() as conn:
        reason = await conn.scalar(text("SELECT reject_reason FROM orders"))
    assert reason == "insufficient cash"


async def test_updating_unknown_order_fails(store: Store) -> None:
    with pytest.raises(KeyError, match="unknown order"):
        await store.update_order(
            "nope", at=NOW, status=OrderStatus.FILLED, filled_quantity=1, average_fill_price=None
        )


async def test_overfill_is_impossible(store: Store) -> None:
    await store.add_order(entry(), at=NOW)
    with pytest.raises(IntegrityError):
        await store.update_order(
            "trend-1",
            at=NOW,
            status=OrderStatus.FILLED,
            filled_quantity=11,
            average_fill_price=D(100),
        )


async def test_fills_are_booked_once_and_net_positions(store: Store) -> None:
    await store.add_order(entry(), at=NOW)
    await store.add_order(entry("x-1", kind="exit", side="sell", stop_price=None), at=NOW)
    buy = Fill("e1", "trend-1", "AAPL", Side.BUY, 10, D(100), D(1), NOW)
    sell = Fill("e2", "x-1", "AAPL", Side.SELL, 4, D(101), D(1), NOW + timedelta(minutes=1))
    assert await store.record_fill(buy)
    assert not await store.record_fill(buy)
    assert await store.record_fill(sell)
    assert await store.booked_positions() == {"AAPL": 6}
    assert await store.fills_since(NOW + timedelta(seconds=30)) == [sell]


async def test_closed_positions_are_not_listed(store: Store) -> None:
    await store.add_order(entry(), at=NOW)
    await store.add_order(entry("x-1", kind="exit", side="sell", stop_price=None), at=NOW)
    await store.record_fill(Fill("e1", "trend-1", "AAPL", Side.BUY, 10, D(100), D(1), NOW))
    await store.record_fill(Fill("e2", "x-1", "AAPL", Side.SELL, 10, D(99), D(1), NOW))
    assert await store.booked_positions() == {}


async def test_fill_for_unknown_order_is_rejected(store: Store) -> None:
    with pytest.raises(IntegrityError):
        await store.record_fill(Fill("e9", "ghost", "AAPL", Side.BUY, 1, D(1), D(0), NOW))


# -- migrations and configuration --------------------------------------------------------------


def test_migrations_downgrade_and_upgrade_cleanly(database_url: str) -> None:
    config = Config(ALEMBIC_INI)
    config.attributes["database_url"] = database_url
    command.downgrade(config, "base")
    migrate(database_url)


def test_schema_matches_the_models(database_url: str) -> None:
    config = Config(ALEMBIC_INI)
    config.attributes["database_url"] = database_url
    command.check(config)  # raises if the models and the migrations disagree


@pytest.mark.parametrize("url", ["", "sqlite:///x.db", "postgresql://u@h/db"])
def test_database_url_must_be_async_postgres(url: str) -> None:
    with pytest.raises(DatabaseConfigError):
        database_url_from_env({"JARVIS_DATABASE_URL": url})


def test_database_url_from_env() -> None:
    url = "postgresql+asyncpg://jarvis@db/jarvis"
    assert database_url_from_env({"JARVIS_DATABASE_URL": url}) == url


async def test_known_order_raises_for_unknown_ids(store: Store) -> None:
    with pytest.raises(KeyError, match="unknown order"):
        await store.known_order("ghost")
    await store.add_order(entry(), at=NOW)
    assert (await store.known_order("trend-1")).symbol == "AAPL"


async def test_stop_price_updates_and_order_counts(store: Store) -> None:
    await store.add_order(entry(), at=NOW)
    await store.add_order(
        entry("trend-1.stop", kind="stop", side="sell", parent_id="trend-1", limit_price=None),
        at=NOW,
    )
    await store.add_order(entry("later", kind="entry"), at=NOW + timedelta(minutes=5))
    await store.set_stop_price("trend-1.stop", D(98), at=NOW)
    stop = await store.known_order("trend-1.stop")
    assert stop.stop_price == D(98)
    assert await store.count_orders_since(NOW) == 2  # stops are not counted
    assert await store.count_orders_since(NOW + timedelta(minutes=1)) == 1
    with pytest.raises(KeyError):
        await store.set_stop_price("ghost", D(1), at=NOW)
