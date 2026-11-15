"""Builds the app's responses from stored state. Nothing here is invented: when data is
missing the field is null and the app shows its empty state (rule 1, §0)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from jarvis.api.schemas import (
    MarketOut,
    PortfolioOut,
    PositionOut,
    ReasonOut,
    StatusOut,
    TodayOut,
    TradeOut,
    TradesOut,
)
from jarvis.config.settings import Settings
from jarvis.markets.calendar import CalendarRangeError, Exchange, next_open, session_at
from jarvis.risk.reasons import Reason, message_sv
from jarvis.store.periods import day_start
from jarvis.store.repo import Store, TradeRecord

STATE_MAX_AGE = timedelta(minutes=3)
CENT = Decimal("0.01")
NO_STATE_SV = "Jag har ingen lägesrapport från handelsdelen ännu."
STALE_STATE_SV = "Jag har inte fått någon färsk lägesrapport från handelsdelen på flera minuter."
MARKET_NAMES_SV = {Exchange.NYSE: "USA", Exchange.STOCKHOLM: "Stockholm"}
STRATEGY_NAMES_SV = {"trend": "Trendföljning"}


def strategy_sv(strategy: str | None) -> str | None:
    """Adam sees strategy names in Swedish; an unknown id is shown as it is."""
    return None if strategy is None else STRATEGY_NAMES_SV.get(strategy, strategy)


class Views:
    def __init__(self, store: Store, settings: Settings, clock: Callable[[], datetime]) -> None:
        self._store = store
        self._settings = settings
        self._clock = clock

    def _exchanges(self) -> list[Exchange]:
        markets = self._settings.markets
        exchanges = []
        if markets.us_equities:
            exchanges.append(Exchange.NYSE)
        if markets.nordic_equities:
            exchanges.append(Exchange.STOCKHOLM)
        return exchanges

    def _market(self, exchange: Exchange, now: datetime) -> MarketOut:
        name = MARKET_NAMES_SV[exchange]
        try:
            today = session_at(exchange, now)
            if today.is_open(now):
                return MarketOut(
                    exchange=exchange.value,
                    name_sv=name,
                    is_open=True,
                    opens_at=today.opens_at,
                    closes_at=today.closes_at,
                )
            opens = next_open(exchange, now)
            following = session_at(exchange, opens)
        except CalendarRangeError:
            return MarketOut(
                exchange=exchange.value, name_sv=name, is_open=False, opens_at=None, closes_at=None
            )
        return MarketOut(
            exchange=exchange.value,
            name_sv=name,
            is_open=False,
            opens_at=opens,
            closes_at=following.closes_at,
        )

    async def status(self) -> StatusOut:
        now = self._clock()
        controls = await self._store.controls()
        markets = [self._market(e, now) for e in self._exchanges()]
        stored = await self._store.account_state()
        if stored is None or now - stored[0] > STATE_MAX_AGE:
            text = NO_STATE_SV if stored is None else STALE_STATE_SV
            return StatusOut(
                mode="live" if controls.trading_mode == "live" else "paper",
                trading_state="halted",
                reasons=[ReasonOut(code="no_state", message_sv=text)],
                broker_connected=False,
                markets=markets,
                briefing_sv=f"{text} Inga nya affärer tas förrän den är tillbaka.",
                as_of=now,
            )
        at, payload = stored
        reasons = [ReasonOut(code=r, message_sv=message_sv(Reason(r))) for r in payload["reasons"]]
        return StatusOut(
            mode="live" if controls.trading_mode == "live" else "paper",
            trading_state=payload["trading_state"],
            reasons=reasons,
            broker_connected=payload["broker_connected"],
            markets=markets,
            briefing_sv=_briefing(payload, markets, now),
            as_of=at,
        )

    async def portfolio(self) -> PortfolioOut:
        now = self._clock()
        stored = await self._store.account_state()
        marks = await self._store.equity_marks(now)
        if stored is None:
            return PortfolioOut(
                base_currency="SEK",
                net_liquidation=None,
                cash=None,
                day_change=None,
                day_change_pct=None,
                positions=[],
                as_of=now,
            )
        at, payload = stored
        change = pct = None
        if marks is not None:
            change = _exact(marks.current - marks.day_start)
            pct = (change / marks.day_start * 100).quantize(CENT)
        return PortfolioOut(
            base_currency=payload["base_currency"],
            net_liquidation=_exact(Decimal(payload["net_liquidation"])),
            cash=_exact(Decimal(payload["cash"])),
            day_change=change,
            day_change_pct=pct,
            positions=[_position(p) for p in payload["positions"]],
            as_of=at,
        )

    async def trades(self, limit: int) -> TradesOut:
        records = await self._store.recent_trades(limit)
        return TradesOut(trades=[_trade(r) for r in records])

    async def today(self) -> TodayOut:
        now = self._clock()
        return TodayOut(
            trades_count=await self._store.count_fills_since(day_start(now)),
            realized_pnl=None,  # needs lot matching; built with the economics module
            risk_level_sv="Standard",
        )


def _exact(value: Decimal) -> Decimal:
    """Drop the database's trailing zeros but keep at least two decimals: 482.3500 -> 482.35,
    while 0.123456 keeps its precision."""
    cents = value.quantize(CENT)
    return cents if cents == value else value.normalize()


def _sv(value: Decimal) -> str:
    """A price written the Swedish way for sentences, e.g. 512,40."""
    return f"{value.quantize(CENT):,}".replace(",", " ").replace(".", ",")


def _money(value: str | None) -> Decimal | None:
    return None if value is None else Decimal(value)


def _position(p: dict[str, Any]) -> PositionOut:
    return PositionOut(
        symbol=p["symbol"],
        quantity=p["quantity"],
        currency=p["currency"] or "",
        average_price=Decimal(p["average_price"]),
        last_price=_money(p["last_price"]),
        market_value=_money(p["market_value"]),
        unrealized_pnl=_money(p["unrealized_pnl"]),
        unrealized_pnl_pct=_money(p["unrealized_pnl_pct"]),
        stop_price=_money(p["stop_price"]),
        strategy=strategy_sv(p["strategy"]),
    )


def _trade(record: TradeRecord) -> TradeOut:
    fill = record.fill
    if record.kind == "entry":
        explanation = record.explanation_sv
    elif record.kind == "stop":
        explanation = f"Stoppen hos mäklaren utlöstes. Såld till {_sv(fill.price)}."
    elif record.kind == "take_profit" and record.limit_price is not None:
        explanation = f"Målkursen {_sv(record.limit_price)} nåddes."
    else:
        explanation = record.explanation_sv
    return TradeOut(
        id=fill.fill_id,
        symbol=fill.symbol,
        side="buy" if fill.side.value == "buy" else "sell",
        quantity=fill.quantity,
        price=_exact(fill.price),
        commission=_exact(fill.commission),
        currency=record.currency or "",
        at=fill.at,
        strategy=strategy_sv(record.strategy),
        explanation_sv=explanation,
    )


def _count_sv(n: int) -> str:
    words = ["Inga", "En", "Två", "Tre", "Fyra", "Fem", "Sex", "Sju", "Åtta", "Nio", "Tio"]
    return words[n] if n < len(words) else str(n)


def _briefing(payload: dict[str, Any], markets: list[MarketOut], now: datetime) -> str:
    n = len(payload["positions"])
    held = "En position är öppen." if n == 1 else f"{_count_sv(n)} positioner är öppna."
    if payload["trading_state"] == "active":
        risk = "Allt inom riskramarna."
    else:
        risk = "Inga nya affärer tas just nu."
    upcoming = [m for m in markets if not m.is_open and m.opens_at is not None]
    open_now = [m for m in markets if m.is_open]
    if open_now:
        when = f"{open_now[0].name_sv} är öppen."
    elif upcoming:
        first = min(upcoming, key=lambda m: m.opens_at or now)
        hours = int(((first.opens_at or now) - now).total_seconds() // 3600)
        when = (
            f"{first.name_sv} öppnar om {hours} timmar."
            if hours >= 1
            else f"{first.name_sv} öppnar inom en timme."
        )
    else:
        when = ""
    return " ".join(part for part in (held, risk, when) if part)
