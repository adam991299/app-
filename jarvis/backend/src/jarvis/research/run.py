"""Validate the trend strategy on real IBKR history and record the outcome (§6.3, §6.5).

Run on the server, next to the gateway:  python -m jarvis.research.run
Every variant tried is stored, the result decides whether the strategy may trade, and the
Swedish report is printed and saved. Index comparison uses SPY's price history (the S&P 500
as a yardstick; Adam's own index fund is chosen in the economics module).
"""

from __future__ import annotations

import asyncio
import dataclasses
import os
import sys
from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from jarvis.config import load_settings_from_env
from jarvis.config.settings import Validation
from jarvis.domain import AssetClass, Instrument
from jarvis.research.validation import ValidationReport, report_sv, validate
from jarvis.runner.loop import MarketSource
from jarvis.store.repo import Store
from jarvis.strategy.bars import Bar
from jarvis.strategy.trend import NAME, TrendParameters, params_dict

HISTORY_YEARS = 10
BENCHMARK = Instrument("SPY", "SMART", "USD", AssetClass.ETF, "index")
GRID = [
    TrendParameters(entry_lookback=e, exit_lookback=x, atr_period=20, atr_stop_multiple=Decimal(m))
    for e in (20, 55)
    for x in (10, 20)
    for m in (2, 3)
]


async def run_validation(
    *,
    market: MarketSource,
    store: Store,
    symbols: Sequence[str],
    rules: Validation,
    clock: Callable[[], datetime],
    grid: Sequence[TrendParameters] = GRID,
) -> tuple[ValidationReport[TrendParameters], str]:
    today: date = clock().date()
    series: dict[str, list[Bar]] = {}
    for symbol in symbols:
        instrument = await market.instrument(symbol)
        if instrument is None:
            continue
        bars = await market.daily_bars(instrument, years=HISTORY_YEARS, closed_through=today)
        if bars:
            series[symbol] = bars
    benchmark = await market.daily_bars(BENCHMARK, years=HISTORY_YEARS, closed_through=today)
    report = validate(
        series,
        grid,
        rules,
        benchmark=benchmark or None,
        earlier_trial_sharpes=await store.trial_sharpes(NAME),
    )
    text = report_sv("Trendföljning", report) + (
        f"\n\nData: {len(series)} aktier, {HISTORY_YEARS} år dagsdata från IBKR."
    )
    now = clock()
    await store.record_trials(
        NAME,
        [
            {
                "params": params_dict(t.params),
                "sample": t.sample,
                "window": t.window,
                "sharpe": t.sharpe,
                "trades": t.trades,
            }
            for t in report.trials
        ],
        at=now,
    )
    await store.save_validation(
        NAME,
        params=params_dict(report.chosen) if report.chosen else None,
        passed=report.passed,
        edge_r=report.edge_r,
        report_sv=text,
        at=now,
    )
    return report, text


async def _main() -> int:  # pragma: no cover - needs a live gateway
    from ib_async import IB

    from jarvis.broker.ibkr import IbkrBroker
    from jarvis.marketdata.ibkr import IbkrMarket
    from jarvis.runner.service import DEFAULT_UNIVERSE, ibkr_settings_from_env, load_symbols
    from jarvis.store.db import create_engine, database_url_from_env

    settings = load_settings_from_env()
    env = os.environ
    ib = IB()
    ibkr = ibkr_settings_from_env(env)
    broker = IbkrBroker(ib, dataclasses.replace(ibkr, client_id=ibkr.client_id + 10))
    await broker.connect()
    try:
        _, text = await run_validation(
            market=IbkrMarket(ib, lambda: datetime.now(UTC)),
            store=Store(create_engine(database_url_from_env(env))),
            symbols=load_symbols(Path(env.get("JARVIS_UNIVERSE", str(DEFAULT_UNIVERSE)))),
            rules=settings.validation,
            clock=lambda: datetime.now(UTC),
        )
    finally:
        await broker.disconnect()
    sys.stdout.write(text + "\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(asyncio.run(_main()))
