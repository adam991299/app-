from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from ib_async import BarData, Contract, ContractDetails, Ticker

from jarvis.marketdata.ibkr import IbkrMarket
from tests.factories import instrument

D = Decimal
NOW = datetime(2026, 11, 16, 16, tzinfo=UTC)


@dataclass
class FakeMarket:
    tickers: dict[str, Ticker] = field(default_factory=dict)
    bars: list[BarData] = field(default_factory=list)
    details: list[ContractDetails] = field(default_factory=list)
    fail: bool = False
    hang: bool = False
    chunks: list[list[BarData]] = field(default_factory=list)
    requests: list[tuple[str, str, str]] = field(default_factory=list)

    async def reqTickersAsync(self, *contracts: Contract) -> list[Ticker]:
        if self.fail:
            raise ConnectionError("down")
        if self.hang:
            await asyncio.sleep(60)
        key = contracts[0].symbol + getattr(contracts[0], "currency", "")
        found = self.tickers.get(contracts[0].symbol) or self.tickers.get(key)
        return [found] if found else []

    async def reqHistoricalDataAsync(
        self,
        contract: Contract,
        *,
        endDateTime: str,
        durationStr: str,
        barSizeSetting: str,
        whatToShow: str,
        useRTH: bool,
        formatDate: int = 1,
    ) -> list[BarData]:
        if self.fail:
            raise ConnectionError("down")
        self.requests.append((endDateTime, durationStr, barSizeSetting))
        if self.chunks:
            return self.chunks.pop(0)
        return self.bars

    async def reqContractDetailsAsync(self, contract: Contract) -> list[ContractDetails]:
        if self.fail:
            raise ConnectionError("down")
        return self.details


def ticker(price: float, data_type: int = 1) -> Ticker:
    made = Ticker()  # ib_async resets fields given to the constructor
    made.marketDataType = data_type
    made.last = price
    return made


def market(fake: FakeMarket, timeout: float = 1.0) -> IbkrMarket:
    return IbkrMarket(fake, lambda: NOW, base_currency="SEK", timeout_seconds=timeout)


async def test_live_quote_with_fx_to_sek() -> None:
    fake = FakeMarket(tickers={"AAPL": ticker(100.25), "USD": ticker(10.5)})
    quote = await market(fake).quote(instrument())
    assert quote is not None
    assert (quote.last, quote.fx_to_base, quote.at) == (D("100.25"), D("10.5"), NOW)


async def test_quote_in_base_currency_needs_no_fx() -> None:
    sek = instrument("VOLV-B")
    sek = type(sek)("VOLV-B", "SFB", "SEK", sek.asset_class, "industrials")
    fake = FakeMarket(tickers={"VOLV-B": ticker(250.0)})
    quote = await market(fake).quote(sek)
    assert quote is not None
    assert quote.fx_to_base == D(1)


async def test_quotes_fail_closed() -> None:
    assert await market(FakeMarket()).quote(instrument()) is None  # no data
    delayed = FakeMarket(tickers={"AAPL": ticker(100.0, data_type=3)})
    assert await market(delayed).quote(instrument()) is None  # delayed is never "now"
    assert await market(FakeMarket(tickers={"AAPL": ticker(math.nan)})).quote(instrument()) is None
    assert await market(FakeMarket(tickers={"AAPL": ticker(0.0)})).quote(instrument()) is None
    no_fx = FakeMarket(tickers={"AAPL": ticker(100.0)})
    assert await market(no_fx).quote(instrument()) is None
    assert await market(FakeMarket(fail=True)).quote(instrument()) is None
    assert await market(FakeMarket(hang=True), timeout=0.05).quote(instrument()) is None


async def test_daily_bars_stop_at_the_last_closed_session() -> None:
    fake = FakeMarket(
        bars=[
            BarData(date=date(2026, 11, 12), open=10, high=11, low=9, close=10.5, volume=100),
            BarData(
                date=datetime(2026, 11, 13, tzinfo=UTC),
                open=10,
                high=12,
                low=9,
                close=11,
                volume=200,
            ),
            BarData(date=date(2026, 11, 16), open=11, high=13, low=10, close=12, volume=300),
        ]
    )
    bars = await market(fake).daily_bars(instrument(), years=1, closed_through=date(2026, 11, 13))
    assert [(b.day, b.close, b.volume) for b in bars] == [
        (date(2026, 11, 12), D("10.5"), 100),
        (date(2026, 11, 13), D("11"), 200),
    ]
    assert (
        await market(FakeMarket(fail=True)).daily_bars(
            instrument(), years=1, closed_through=date(2026, 11, 13)
        )
        == []
    )


async def test_instrument_uses_ibkr_industry_as_sector() -> None:
    fake = FakeMarket(details=[ContractDetails(industry="Technology")])
    found = await market(fake).instrument("AAPL")
    assert found is not None
    assert (found.symbol, found.sector, found.currency) == ("AAPL", "technology", "USD")
    assert await market(FakeMarket(details=[ContractDetails(industry="")])).instrument("X") is None
    assert await market(FakeMarket()).instrument("X") is None
    assert await market(FakeMarket(fail=True)).instrument("X") is None


def five_minutes(start: datetime, count: int) -> list[BarData]:
    return [
        BarData(start + i * timedelta(minutes=5), 100.0, 101.0, 99.0, 100.5, 1000)
        for i in range(count)
    ]


async def test_intraday_bars_keep_only_finished_bars_in_utc() -> None:
    opens = datetime(2026, 11, 16, 14, 30, tzinfo=UTC)
    fake = FakeMarket(bars=five_minutes(opens, 19))  # the 19th bar (16:00) is still running
    bars = await market(fake).intraday_bars(instrument(), now=NOW)
    assert len(bars) == 18
    assert bars[-1].at == datetime(2026, 11, 16, 15, 55, tzinfo=UTC)
    assert fake.requests == [("", "1 D", "5 mins")]


async def test_intraday_history_is_fetched_a_month_at_a_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pauses: list[float] = []

    async def no_wait(seconds: float) -> None:
        pauses.append(seconds)

    monkeypatch.setattr("jarvis.marketdata.ibkr.asyncio.sleep", no_wait)
    recent = five_minutes(datetime(2026, 11, 16, 14, 30, tzinfo=UTC), 3)
    older = five_minutes(datetime(2026, 10, 16, 14, 30, tzinfo=UTC), 2) + recent[:1]
    fake = FakeMarket(chunks=[recent, older, []])
    bars = await market(fake).intraday_bars(instrument(), now=NOW, days=45)
    assert len(bars) == 5  # the shared boundary bar is kept once
    assert [r[1] for r in fake.requests] == ["20 D", "20 D", "5 D"]
    assert fake.requests[1][0] == "20261116-14:30:00"
    assert pauses == [11.0, 11.0]


async def test_intraday_bars_fail_closed() -> None:
    assert await market(FakeMarket(fail=True)).intraday_bars(instrument(), now=NOW) == []
