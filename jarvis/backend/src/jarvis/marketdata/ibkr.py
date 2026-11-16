"""Quotes, daily bars and instrument details from IBKR (spec §4.1).

Fails closed: if a quote is missing, not real-time, or slow, ``quote`` returns None and
the risk engine refuses to trade (MISSING_QUOTE). Delayed data is never passed off as
current, because its timestamp would look fresh while the price is 15 minutes old.
"""

from __future__ import annotations

import asyncio
import logging
import math
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, Protocol

from ib_async import Contract, Forex, Stock

from jarvis.domain import AssetClass, Instrument, Quote
from jarvis.strategy.bars import Bar
from jarvis.strategy.orb import BAR, IntradayBar

logger = logging.getLogger(__name__)
LIVE = 1  # IBKR market data type: 1 live, 2 frozen, 3 delayed, 4 delayed frozen
PACING_SECONDS = 11.0  # IBKR: at most 60 history requests per 10 minutes


class MarketClient(Protocol):
    """The part of ``ib_async.IB`` used for market data (lets tests supply a fake)."""

    def reqTickersAsync(self, *contracts: Contract) -> Awaitable[list[Any]]: ...  # noqa: N802

    def reqHistoricalDataAsync(  # noqa: N802
        self,
        contract: Contract,
        *,
        endDateTime: str,  # noqa: N803
        durationStr: str,  # noqa: N803
        barSizeSetting: str,  # noqa: N803
        whatToShow: str,  # noqa: N803
        useRTH: bool,  # noqa: N803
        formatDate: int = 1,  # noqa: N803
    ) -> Awaitable[list[Any]]: ...

    def reqContractDetailsAsync(self, contract: Contract) -> Awaitable[list[Any]]: ...  # noqa: N802


class IbkrMarket:
    def __init__(
        self,
        ib: MarketClient,
        clock: Callable[[], datetime],
        base_currency: str = "SEK",
        timeout_seconds: float = 15.0,  # IBKR snapshots can take about 11 s
    ) -> None:
        self._ib = ib
        self._clock = clock
        self._base = base_currency
        self._timeout = timeout_seconds

    async def _price(self, contract: Contract) -> Decimal | None:
        try:
            tickers = await asyncio.wait_for(self._ib.reqTickersAsync(contract), self._timeout)
        except Exception:
            logger.exception("quote request failed for %s", contract.symbol)
            return None
        if not tickers:
            return None
        ticker = tickers[0]
        if ticker.marketDataType != LIVE:
            return None
        price = ticker.marketPrice()
        if price is None or math.isnan(price) or price <= 0:
            return None
        return Decimal(str(price))

    async def quote(self, instrument: Instrument) -> Quote | None:
        price = await self._price(Stock(instrument.symbol, "SMART", instrument.currency))
        if price is None:
            return None
        fx = Decimal(1)
        if instrument.currency != self._base:
            rate = await self._price(Forex(f"{instrument.currency}{self._base}"))
            if rate is None:
                return None
            fx = rate
        return Quote(instrument.symbol, price, fx, self._clock())

    async def daily_bars(
        self, instrument: Instrument, *, years: int, closed_through: date
    ) -> list[Bar]:
        """Split- and dividend-adjusted daily bars up to and including ``closed_through``
        (the last session that has closed). Empty on any failure: no data, no trade."""
        contract = Stock(instrument.symbol, "SMART", instrument.currency)
        try:
            rows = await asyncio.wait_for(
                self._ib.reqHistoricalDataAsync(
                    contract,
                    endDateTime="",
                    durationStr=f"{years} Y",
                    barSizeSetting="1 day",
                    whatToShow="ADJUSTED_LAST",
                    useRTH=True,
                ),
                self._timeout * 6,
            )
        except Exception:
            logger.exception("history request failed for %s", instrument.symbol)
            return []
        bars = []
        for row in rows:
            day = row.date.date() if isinstance(row.date, datetime) else row.date
            if day > closed_through:
                continue
            bars.append(
                Bar(
                    day=day,
                    open=Decimal(str(row.open)),
                    high=Decimal(str(row.high)),
                    low=Decimal(str(row.low)),
                    close=Decimal(str(row.close)),
                    volume=int(row.volume),
                )
            )
        return bars

    async def intraday_bars(
        self, instrument: Instrument, *, now: datetime, days: int = 1
    ) -> list[IntradayBar]:
        """Finished 5-minute bars of the regular session, in UTC. ``days`` > 1 is for
        research; IBKR's pacing rules are respected by asking one month at a time."""
        contract = Stock(instrument.symbol, "SMART", instrument.currency)
        bars: list[IntradayBar] = []
        end = ""
        remaining = days
        while remaining > 0:
            chunk = min(remaining, 20)
            try:
                rows = await asyncio.wait_for(
                    self._ib.reqHistoricalDataAsync(
                        contract,
                        endDateTime=end,
                        durationStr=f"{chunk} D",
                        barSizeSetting="5 mins",
                        whatToShow="TRADES",
                        useRTH=True,
                        formatDate=2,  # UTC timestamps
                    ),
                    self._timeout * 6,
                )
            except Exception:
                logger.exception("intraday request failed for %s", instrument.symbol)
                return []
            chunk_bars = [
                IntradayBar(
                    at=row.date.astimezone(UTC),
                    open=Decimal(str(row.open)),
                    high=Decimal(str(row.high)),
                    low=Decimal(str(row.low)),
                    close=Decimal(str(row.close)),
                    volume=int(row.volume),
                )
                for row in rows
                if row.date + BAR <= now
            ]
            if not chunk_bars:
                break
            bars = chunk_bars + bars
            end = chunk_bars[0].at.strftime("%Y%m%d-%H:%M:%S")
            remaining -= chunk
            if remaining > 0:
                await asyncio.sleep(PACING_SECONDS)
        unique = {bar.at: bar for bar in bars}  # chunks may share their boundary bar
        return [unique[at] for at in sorted(unique)]

    async def instrument(self, symbol: str, currency: str = "USD") -> Instrument | None:
        """Instrument with IBKR's industry as sector (needed for the sector limit)."""
        try:
            details = await asyncio.wait_for(
                self._ib.reqContractDetailsAsync(Stock(symbol, "SMART", currency)), self._timeout
            )
        except Exception:
            logger.exception("contract details failed for %s", symbol)
            return None
        if len(details) != 1 or not details[0].industry:
            return None
        return Instrument(
            symbol=symbol,
            exchange="SMART",
            currency=currency,
            asset_class=AssetClass.EQUITY,
            sector=details[0].industry,
        )
