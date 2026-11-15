"""The pre-trade check every order must pass (spec §7). Fails closed: any doubt rejects.

An order either opens/increases a long position (BUY) or reduces one (SELL). Closing is
allowed in every state except HALTED, because it lowers risk. Opening must pass every
check. All failing checks are reported, not just the first, so the log says exactly why.

Working orders (``pending``) are counted as if filled, so two identical signals can never
together exceed a limit. Protective stop and target orders attached to positions are not
``pending``; they are part of the position they protect.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from jarvis.config.settings import Risk
from jarvis.domain import Account, AssetClass, Instrument, Position, Quote, Side
from jarvis.risk.breakers import BreakerStatus
from jarvis.risk.reasons import Reason
from jarvis.risk.sizing import gap_fraction, position_cap_fraction
from jarvis.risk.units import fraction


@dataclass(frozen=True, slots=True)
class OrderProposal:
    instrument: Instrument
    side: Side
    quantity: int
    limit_price: Decimal
    stop_price: Decimal | None = None
    expected_edge: Decimal | None = None  # expected net gain in base currency
    estimated_cost: Decimal = Decimal(0)  # commission + spread + slippage, base currency


@dataclass(frozen=True, slots=True)
class PendingOrder:
    """A working entry or exit order at the broker (not a protective child order)."""

    instrument: Instrument
    side: Side
    quantity: int
    limit_price: Decimal


@dataclass(frozen=True, slots=True)
class MarketSession:
    """Today's regular session for the instrument's exchange, in UTC."""

    opens_at: datetime | None
    closes_at: datetime | None

    def is_open(self, now: datetime) -> bool:
        if self.opens_at is None or self.closes_at is None:
            return False
        return self.opens_at <= now < self.closes_at


@dataclass(frozen=True, slots=True)
class RiskContext:
    now: datetime
    account: Account
    positions: Mapping[str, Position]
    pending: Sequence[PendingOrder]
    quotes: Mapping[str, Quote]
    session: MarketSession
    breakers: BreakerStatus
    orders_last_minute: int
    orders_today: int


@dataclass(frozen=True, slots=True)
class RiskDecision:
    approved: bool
    reasons: tuple[Reason, ...]


class RiskEngine:
    def __init__(self, risk: Risk) -> None:
        self._risk = risk

    def check(self, order: OrderProposal, ctx: RiskContext) -> RiskDecision:
        if ctx.now.utcoffset() is None:
            raise ValueError("risk checks need a timezone-aware clock")
        reasons = self._validity(order)
        if reasons:
            return RiskDecision(False, tuple(reasons))
        if order.side is Side.BUY:
            reasons = self._check_open(order, ctx)
        else:
            reasons = self._check_close(order, ctx)
        return RiskDecision(not reasons, tuple(dict.fromkeys(reasons)))

    # -- shared --------------------------------------------------------------------

    @staticmethod
    def _validity(order: OrderProposal) -> list[Reason]:
        reasons: list[Reason] = []
        if order.quantity <= 0:
            reasons.append(Reason.INVALID_QUANTITY)
        if order.limit_price <= 0 or order.estimated_cost < 0:
            reasons.append(Reason.INVALID_PRICE)
        return reasons

    def _market_checks(self, order: OrderProposal, ctx: RiskContext) -> list[Reason]:
        safety = self._risk.order_safety
        reasons: list[Reason] = []
        if not ctx.session.is_open(ctx.now):
            reasons.append(Reason.MARKET_CLOSED)
        if ctx.orders_last_minute >= safety.max_orders_per_minute:
            reasons.append(Reason.ORDER_RATE_MINUTE)
        if ctx.orders_today >= safety.max_orders_per_day:
            reasons.append(Reason.ORDER_RATE_DAY)
        quote = ctx.quotes.get(order.instrument.symbol)
        if quote is None:
            reasons.append(Reason.MISSING_QUOTE)
            return reasons
        max_age = timedelta(seconds=self._risk.circuit_breakers.max_quote_age_seconds)
        if ctx.now - quote.at > max_age:
            reasons.append(Reason.STALE_QUOTE)
        deviation = abs(order.limit_price - quote.last) / quote.last
        if deviation > fraction(safety.max_price_deviation_pct):
            reasons.append(Reason.PRICE_DEVIATION)
        return reasons

    # -- closing -------------------------------------------------------------------

    def _check_close(self, order: OrderProposal, ctx: RiskContext) -> list[Reason]:
        reasons: list[Reason] = []
        if not ctx.breakers.state.allows_closing:
            reasons.extend(ctx.breakers.reasons)
        symbol = order.instrument.symbol
        held = ctx.positions[symbol].quantity if symbol in ctx.positions else 0
        already_selling = sum(
            p.quantity for p in ctx.pending if p.side is Side.SELL and p.instrument.symbol == symbol
        )
        if order.quantity > held - already_selling:
            reasons.append(Reason.SHORT_SELLING_NOT_ALLOWED)
        reasons.extend(self._market_checks(order, ctx))
        return reasons

    # -- opening -------------------------------------------------------------------

    def _check_open(self, order: OrderProposal, ctx: RiskContext) -> list[Reason]:
        reasons: list[Reason] = []
        if not ctx.breakers.state.allows_new_positions:
            reasons.extend(ctx.breakers.reasons)
        reasons.extend(self._market_checks(order, ctx))
        reasons.extend(self._window_check(ctx))
        reasons.extend(self._stop_and_edge(order))

        equity = ctx.account.net_liquidation
        if equity <= 0:
            reasons.append(Reason.NO_EQUITY)
            return reasons
        exposures = _Exposures.build(order, ctx)
        if exposures is None:
            reasons.append(Reason.MISSING_QUOTE)
            return reasons
        reasons.extend(self._limits(order, ctx, exposures, equity))
        return reasons

    def _window_check(self, ctx: RiskContext) -> list[Reason]:
        session, safety = ctx.session, self._risk.order_safety
        if session.opens_at is None or session.closes_at is None:
            return []
        earliest = session.opens_at + timedelta(minutes=safety.avoid_open_minutes)
        latest = session.closes_at - timedelta(minutes=safety.avoid_close_minutes)
        if session.is_open(ctx.now) and not earliest <= ctx.now <= latest:
            return [Reason.OUTSIDE_TRADING_WINDOW]
        return []

    def _stop_and_edge(self, order: OrderProposal) -> list[Reason]:
        reasons: list[Reason] = []
        if order.stop_price is None:
            reasons.append(Reason.MISSING_STOP)
        elif not 0 < order.stop_price < order.limit_price:
            reasons.append(Reason.INVALID_STOP)
        if order.expected_edge is None:
            reasons.append(Reason.MISSING_EDGE)
        else:
            required = order.estimated_cost * Decimal(
                str(self._risk.turnover.min_edge_to_cost_ratio)
            )
            if order.expected_edge <= 0 or order.expected_edge < required:
                reasons.append(Reason.EDGE_TOO_SMALL)
        return reasons

    def _limits(
        self, order: OrderProposal, ctx: RiskContext, exp: _Exposures, equity: Decimal
    ) -> list[Reason]:
        risk, portfolio = self._risk, self._risk.portfolio
        instrument = order.instrument
        reasons: list[Reason] = []

        if order.stop_price is not None and 0 < order.stop_price < order.limit_price:
            trade_risk = order.quantity * (order.limit_price - order.stop_price) * exp.fx
            if trade_risk > equity * fraction(risk.per_trade.max_risk_pct):
                reasons.append(Reason.TRADE_RISK_LIMIT)

        position_value = exp.by_symbol[instrument.symbol]
        if position_value > equity * position_cap_fraction(instrument, risk):
            reasons.append(Reason.POSITION_LIMIT)
        if position_value * gap_fraction(instrument, risk) > equity * fraction(
            risk.gap.max_gap_loss_pct
        ):
            reasons.append(Reason.GAP_LOSS_LIMIT)

        if instrument.asset_class in (AssetClass.EQUITY, AssetClass.ETF):
            if instrument.sector is None:
                reasons.append(Reason.UNKNOWN_SECTOR)
            elif exp.by_sector[instrument.sector] > equity * fraction(portfolio.max_sector_pct):
                reasons.append(Reason.SECTOR_LIMIT)
        crypto_cap = min(portfolio.max_crypto_total_pct, risk.technical_max.crypto_total_pct)
        if instrument.asset_class is AssetClass.CRYPTO and exp.by_class[
            AssetClass.CRYPTO
        ] > equity * fraction(crypto_cap):
            reasons.append(Reason.CRYPTO_LIMIT)
        if instrument.asset_class is AssetClass.COMMODITY and exp.by_class[
            AssetClass.COMMODITY
        ] > equity * fraction(portfolio.max_commodities_total_pct):
            reasons.append(Reason.COMMODITIES_LIMIT)

        if exp.gross > equity * fraction(portfolio.max_gross_exposure_pct):
            reasons.append(Reason.GROSS_EXPOSURE_LIMIT)
        cash_after = ctx.account.cash - exp.pending_buys - exp.order_value - order.estimated_cost
        if cash_after < equity * fraction(portfolio.min_cash_reserve_pct):
            reasons.append(Reason.CASH_RESERVE)

        if exp.open_symbols > risk.concurrency.max_open_positions:
            reasons.append(Reason.MAX_OPEN_POSITIONS)
        return reasons


@dataclass(frozen=True, slots=True)
class _Exposures:
    """Market value in base currency after the order, counting working buys as filled."""

    fx: Decimal
    order_value: Decimal
    pending_buys: Decimal
    gross: Decimal
    by_symbol: dict[str, Decimal]
    by_sector: dict[str, Decimal]
    by_class: dict[AssetClass, Decimal]
    open_symbols: int

    @classmethod
    def build(cls, order: OrderProposal, ctx: RiskContext) -> _Exposures | None:
        legs: list[tuple[Instrument, Decimal]] = []
        for position in ctx.positions.values():
            quote = ctx.quotes.get(position.instrument.symbol)
            if quote is None:
                return None
            legs.append((position.instrument, position.quantity * quote.last_base))
        pending_buys = Decimal(0)
        for pending in ctx.pending:
            if pending.side is not Side.BUY:
                continue
            quote = ctx.quotes.get(pending.instrument.symbol)
            if quote is None:
                return None
            value = pending.quantity * pending.limit_price * quote.fx_to_base
            pending_buys += value
            legs.append((pending.instrument, value))
        own_quote = ctx.quotes.get(order.instrument.symbol)
        if own_quote is None:
            return None
        order_value = order.quantity * order.limit_price * own_quote.fx_to_base
        legs.append((order.instrument, order_value))

        by_symbol: dict[str, Decimal] = {}
        by_sector: dict[str, Decimal] = {}
        by_class: dict[AssetClass, Decimal] = dict.fromkeys(AssetClass, Decimal(0))
        for instrument, value in legs:
            by_symbol[instrument.symbol] = by_symbol.get(instrument.symbol, Decimal(0)) + value
            if instrument.sector is not None:
                by_sector[instrument.sector] = by_sector.get(instrument.sector, Decimal(0)) + value
            by_class[instrument.asset_class] += value
        return cls(
            fx=own_quote.fx_to_base,
            order_value=order_value,
            pending_buys=pending_buys,
            gross=sum((value for _, value in legs), Decimal(0)),
            by_symbol=by_symbol,
            by_sector=by_sector,
            by_class=by_class,
            open_symbols=len(by_symbol),
        )
