"""Reading and writing Jarvis's state. Every change to Adam's controls is written to the
audit log in the same transaction, so the log can never miss a change (§10)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import case, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from jarvis.broker.models import Fill, OrderStatus
from jarvis.domain import Side
from jarvis.risk.breakers import EquityMarks
from jarvis.store.db import session_factory
from jarvis.store.periods import day_start, week_start
from jarvis.store.tables import (
    AuditEntry,
    Controls,
    EquitySnapshot,
    FillRow,
    OrderRow,
    RiskDecisionRow,
)


@dataclass(frozen=True, slots=True)
class ControlsState:
    trading_mode: str
    paused: bool
    kill_switch_engaged: bool
    kill_switch_reason: str | None
    peak_reset_at: datetime | None


@dataclass(frozen=True, slots=True)
class NewOrder:
    client_order_id: str
    kind: str  # entry, exit, stop, take_profit
    symbol: str
    side: str
    quantity: int
    limit_price: Decimal | None
    stop_price: Decimal | None
    strategy: str | None = None
    parent_id: str | None = None
    explanation_sv: str | None = None
    signal: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class StoredOrder:
    client_order_id: str
    parent_id: str | None
    kind: str
    symbol: str
    side: str
    quantity: int
    status: OrderStatus
    filled_quantity: int
    average_fill_price: Decimal | None
    strategy: str | None
    limit_price: Decimal | None
    stop_price: Decimal | None


def _stored(row: OrderRow) -> StoredOrder:
    return StoredOrder(
        client_order_id=row.client_order_id,
        parent_id=row.parent_id,
        kind=row.kind,
        symbol=row.symbol,
        side=row.side,
        quantity=row.quantity,
        status=OrderStatus(row.status),
        filled_quantity=row.filled_quantity,
        average_fill_price=row.average_fill_price,
        strategy=row.strategy,
        limit_price=row.limit_price,
        stop_price=row.stop_price,
    )


class Store:
    def __init__(self, engine: AsyncEngine) -> None:
        self._sessions = session_factory(engine)

    # -- controls --------------------------------------------------------------------

    async def controls(self) -> ControlsState:
        async with self._sessions() as session:
            row = await session.get_one(Controls, 1)
            return ControlsState(
                trading_mode=row.trading_mode,
                paused=row.paused,
                kill_switch_engaged=row.kill_switch_engaged,
                kill_switch_reason=row.kill_switch_reason,
                peak_reset_at=row.peak_reset_at,
            )

    async def _change_controls(
        self, *, at: datetime, actor: str, action: str, details: dict[str, Any], **values: Any
    ) -> None:
        async with self._sessions.begin() as session:
            await session.execute(
                update(Controls).where(Controls.id == 1).values(updated_at=at, **values)
            )
            session.add(AuditEntry(at=at, actor=actor, action=action, details=details))

    async def set_paused(self, paused: bool, *, actor: str, at: datetime) -> None:
        await self._change_controls(
            at=at,
            actor=actor,
            action="pause" if paused else "resume",
            details={},
            paused=paused,
        )

    async def engage_kill_switch(self, reason: str, *, actor: str, at: datetime) -> None:
        if (await self.controls()).kill_switch_engaged:
            return
        await self._change_controls(
            at=at,
            actor=actor,
            action="kill_switch_engaged",
            details={"reason": reason},
            kill_switch_engaged=True,
            kill_switch_reason=reason,
        )

    async def reset_kill_switch(self, *, actor: str, at: datetime) -> None:
        """Adam restarts trading. The equity peak is re-based to now, so the drawdown that
        tripped the switch does not trip it again immediately (§7)."""
        await self._change_controls(
            at=at,
            actor=actor,
            action="kill_switch_reset",
            details={},
            kill_switch_engaged=False,
            kill_switch_reason=None,
            peak_reset_at=at,
        )

    async def audit(
        self, *, actor: str, action: str, at: datetime, details: dict[str, Any] | None = None
    ) -> None:
        async with self._sessions.begin() as session:
            session.add(AuditEntry(at=at, actor=actor, action=action, details=details or {}))

    async def audit_entries(self, limit: int = 100) -> list[tuple[str, str, dict[str, Any]]]:
        async with self._sessions() as session:
            rows = await session.scalars(
                select(AuditEntry).order_by(AuditEntry.id.desc()).limit(limit)
            )
            return [(r.actor, r.action, r.details) for r in rows]

    # -- equity ------------------------------------------------------------------------

    async def record_equity(self, *, at: datetime, net_liquidation: Decimal, cash: Decimal) -> None:
        async with self._sessions.begin() as session:
            session.add(EquitySnapshot(at=at, net_liquidation=net_liquidation, cash=cash))

    async def equity_marks(self, now: datetime) -> EquityMarks | None:
        """The circuit breakers' reference values, or None before the first snapshot."""
        async with self._sessions() as session:
            current = await _latest_before(session, now, inclusive=True)
            if current is None:
                return None
            controls = await session.get_one(Controls, 1)
            day_ref, day_low = await _period(session, day_start(now), now, current)
            week_ref, week_low = await _period(session, week_start(now), now, current)
            peak_query = select(func.max(EquitySnapshot.net_liquidation)).where(
                EquitySnapshot.at <= now
            )
            if controls.peak_reset_at is not None:
                peak_query = peak_query.where(EquitySnapshot.at >= controls.peak_reset_at)
            peak = (await session.scalar(peak_query)) or current
            return EquityMarks(
                day_start=day_ref,
                day_low=day_low,
                week_start=week_ref,
                week_low=min(week_low, day_low),
                peak=max(peak, current),
                current=current,
            )

    # -- risk decisions ----------------------------------------------------------------

    async def record_risk_decision(
        self,
        *,
        at: datetime,
        client_order_id: str,
        symbol: str,
        side: str,
        quantity: int,
        approved: bool,
        reasons: list[str],
        trading_state: str,
    ) -> None:
        async with self._sessions.begin() as session:
            session.add(
                RiskDecisionRow(
                    at=at,
                    client_order_id=client_order_id,
                    symbol=symbol,
                    side=side,
                    quantity=quantity,
                    approved=approved,
                    reasons=reasons,
                    trading_state=trading_state,
                )
            )

    async def risk_decisions(self, client_order_id: str) -> list[tuple[bool, list[str]]]:
        async with self._sessions() as session:
            rows = await session.scalars(
                select(RiskDecisionRow)
                .where(RiskDecisionRow.client_order_id == client_order_id)
                .order_by(RiskDecisionRow.id)
            )
            return [(r.approved, list(r.reasons)) for r in rows]

    # -- orders and fills --------------------------------------------------------------

    async def add_order(self, order: NewOrder, *, at: datetime) -> bool:
        """Journal a new order before it is sent. False if the id already exists (a
        restart replaying the same signal), so the caller never sends it twice."""
        async with self._sessions.begin() as session:
            result = await session.execute(
                insert(OrderRow)
                .values(
                    client_order_id=order.client_order_id,
                    parent_id=order.parent_id,
                    strategy=order.strategy,
                    kind=order.kind,
                    symbol=order.symbol,
                    side=order.side,
                    quantity=order.quantity,
                    limit_price=order.limit_price,
                    stop_price=order.stop_price,
                    status=OrderStatus.NEW.value,
                    filled_quantity=0,
                    explanation_sv=order.explanation_sv,
                    signal=order.signal or {},
                    created_at=at,
                    updated_at=at,
                )
                .on_conflict_do_nothing(index_elements=[OrderRow.client_order_id])
            )
            return bool(result.rowcount)  # type: ignore[attr-defined]

    async def update_order(
        self,
        client_order_id: str,
        *,
        at: datetime,
        status: OrderStatus,
        filled_quantity: int,
        average_fill_price: Decimal | None,
        quantity: int | None = None,
        reject_reason: str | None = None,
    ) -> None:
        values: dict[str, Any] = {
            "status": status.value,
            "filled_quantity": filled_quantity,
            "average_fill_price": average_fill_price,
            "updated_at": at,
        }
        if quantity is not None:
            values["quantity"] = quantity
        if reject_reason is not None:
            values["reject_reason"] = reject_reason
        async with self._sessions.begin() as session:
            result = await session.execute(
                update(OrderRow).where(OrderRow.client_order_id == client_order_id).values(**values)
            )
            if not result.rowcount:  # type: ignore[attr-defined]
                raise KeyError(f"unknown order {client_order_id}")

    async def set_stop_price(
        self, client_order_id: str, stop_price: Decimal, *, at: datetime
    ) -> None:
        async with self._sessions.begin() as session:
            result = await session.execute(
                update(OrderRow)
                .where(OrderRow.client_order_id == client_order_id)
                .values(stop_price=stop_price, updated_at=at)
            )
            if not result.rowcount:  # type: ignore[attr-defined]
                raise KeyError(f"unknown order {client_order_id}")

    async def count_orders_since(self, since: datetime) -> int:
        """Entries and exits Jarvis created since ``since`` (for the order-rate limits)."""
        async with self._sessions() as session:
            count = await session.scalar(
                select(func.count())
                .select_from(OrderRow)
                .where(OrderRow.created_at >= since, OrderRow.kind.in_(("entry", "exit")))
            )
            return int(count or 0)

    async def known_order(self, client_order_id: str) -> StoredOrder:
        """Like ``order``, for ids Jarvis itself journaled: a missing row is a bug and raises."""
        found = await self.order(client_order_id)
        if found is None:
            raise KeyError(f"unknown order {client_order_id}")
        return found

    async def order(self, client_order_id: str) -> StoredOrder | None:
        async with self._sessions() as session:
            row = await session.get(OrderRow, client_order_id)
            return _stored(row) if row is not None else None

    async def open_orders(self) -> list[StoredOrder]:
        terminal = [s.value for s in OrderStatus if s.is_terminal]
        async with self._sessions() as session:
            rows = await session.scalars(
                select(OrderRow)
                .where(OrderRow.status.not_in(terminal))
                .order_by(OrderRow.created_at, OrderRow.client_order_id)
            )
            return [_stored(r) for r in rows]

    async def record_fill(self, fill: Fill) -> bool:
        """Book a broker fill once. False if it was already booked."""
        async with self._sessions.begin() as session:
            result = await session.execute(
                insert(FillRow)
                .values(
                    fill_id=fill.fill_id,
                    client_order_id=fill.client_order_id,
                    symbol=fill.symbol,
                    side=fill.side.value,
                    quantity=fill.quantity,
                    price=fill.price,
                    commission=fill.commission,
                    at=fill.at,
                )
                .on_conflict_do_nothing(index_elements=[FillRow.fill_id])
            )
            return bool(result.rowcount)  # type: ignore[attr-defined]

    async def booked_positions(self) -> dict[str, int]:
        """Net quantity per symbol from booked fills: what Jarvis believes it holds."""
        signed = func.sum(case((FillRow.side == "buy", FillRow.quantity), else_=-FillRow.quantity))
        async with self._sessions() as session:
            rows = await session.execute(select(FillRow.symbol, signed).group_by(FillRow.symbol))
            return {symbol: int(qty) for symbol, qty in rows if qty}

    async def fills_since(self, since: datetime) -> list[Fill]:
        async with self._sessions() as session:
            rows = await session.scalars(
                select(FillRow).where(FillRow.at >= since).order_by(FillRow.at, FillRow.fill_id)
            )
            return [
                Fill(
                    r.fill_id,
                    r.client_order_id,
                    r.symbol,
                    Side(r.side),
                    r.quantity,
                    r.price,
                    r.commission,
                    r.at,
                )
                for r in rows
            ]


async def _latest_before(
    session: AsyncSession, moment: datetime, *, inclusive: bool
) -> Decimal | None:
    condition = EquitySnapshot.at <= moment if inclusive else EquitySnapshot.at < moment
    value: Decimal | None = await session.scalar(
        select(EquitySnapshot.net_liquidation)
        .where(condition)
        .order_by(EquitySnapshot.at.desc(), EquitySnapshot.id.desc())
        .limit(1)
    )
    return value


async def _period(
    session: AsyncSession, start: datetime, now: datetime, current: Decimal
) -> tuple[Decimal, Decimal]:
    """(reference, low) for a period: the reference is the last value before the period
    began (yesterday's close), or the period's first value if there is none."""
    reference = await _latest_before(session, start, inclusive=False)
    if reference is None:
        reference = await session.scalar(
            select(EquitySnapshot.net_liquidation)
            .where(EquitySnapshot.at >= start, EquitySnapshot.at <= now)
            .order_by(EquitySnapshot.at, EquitySnapshot.id)
            .limit(1)
        )
    low = await session.scalar(
        select(func.min(EquitySnapshot.net_liquidation)).where(
            EquitySnapshot.at >= start, EquitySnapshot.at <= now
        )
    )
    ref = reference if reference is not None else current
    return ref, min(v for v in (ref, low, current) if v is not None)
