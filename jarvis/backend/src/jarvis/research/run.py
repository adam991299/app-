"""Validate a strategy on real IBKR history and record the outcome (§6.3, §6.5).

Run on the server, next to the gateway:
    python -m jarvis.research.run        (trend following, 10 years of daily bars)
    python -m jarvis.research.run orb    (day trading, one year of 5-minute bars; takes about
                                          two hours for 50 symbols because of IBKR pacing)
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
from typing import Any, Protocol

from jarvis.config import load_settings_from_env
from jarvis.config.settings import Validation
from jarvis.domain import AssetClass, Instrument
from jarvis.research.costs import CostModel
from jarvis.research.orb_backtest import evaluate_orb
from jarvis.research.validation import ValidationReport, report_sv, validate
from jarvis.runner.daytrade import IntradaySource
from jarvis.runner.loop import MarketSource
from jarvis.store.repo import Store
from jarvis.strategy import orb
from jarvis.strategy.bars import Bar
from jarvis.strategy.orb import IntradayBar, OrbParameters
from jarvis.strategy.trend import NAME, TrendParameters, params_dict

HISTORY_YEARS = 10
BENCHMARK = Instrument("SPY", "SMART", "USD", AssetClass.ETF, "index")
GRID = [
    TrendParameters(entry_lookback=e, exit_lookback=x, atr_period=20, atr_stop_multiple=Decimal(m))
    for e in (20, 55)
    for x in (10, 20)
    for m in (2, 3)
]
INTRADAY_DAYS = 252
ORB_GRID = [
    OrbParameters(range_minutes=r, target_r=Decimal(t)) for r in (15, 30) for t in ("1.5", "2", "3")
]
ORB_FREE_PARAMETERS = 2  # opening range length, profit target


class ResearchSource(MarketSource, IntradaySource, Protocol):
    """Daily and intraday history from the same source."""


async def run_validation(
    *,
    market: MarketSource,
    store: Store,
    symbols: Sequence[str],
    rules: Validation,
    clock: Callable[[], datetime],
    grid: Sequence[TrendParameters] = GRID,
    costs: CostModel | None = None,
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
        costs=costs,
    )
    text = report_sv("Trendföljning", report) + (
        f"\n\nData: {len(series)} aktier, {HISTORY_YEARS} år dagsdata från IBKR."
    )
    await _record(store, NAME, report, params_dict, text, clock())
    return report, text


async def run_orb_validation(
    *,
    market: ResearchSource,
    store: Store,
    symbols: Sequence[str],
    rules: Validation,
    clock: Callable[[], datetime],
    grid: Sequence[OrbParameters] = ORB_GRID,
    days: int = INTRADAY_DAYS,
    costs: CostModel | None = None,
) -> tuple[ValidationReport[OrbParameters], str]:
    """Walk-forward over about a year of 5-minute bars: six months to choose, one month to
    judge, the last 20 % locked away (§6.3)."""
    now = clock()
    series: dict[str, list[IntradayBar]] = {}
    for symbol in symbols:
        instrument = await market.instrument(symbol)
        if instrument is None:
            continue
        bars = await market.intraday_bars(instrument, now=now, days=days)
        if bars:
            series[symbol] = bars
    benchmark = await market.daily_bars(BENCHMARK, years=2, closed_through=now.date())
    report = validate(
        series,
        grid,
        rules,
        benchmark=benchmark or None,
        earlier_trial_sharpes=await store.trial_sharpes(orb.NAME),
        costs=costs,
        train_days=126,
        test_days=21,
        evaluator=evaluate_orb,
        free_parameters=ORB_FREE_PARAMETERS,
    )
    text = report_sv("Daytrading (öppningsintervall)", report) + (
        f"\n\nData: {len(series)} aktier, {days} handelsdagar med 5-minutersdata från IBKR."
    )
    await _record(store, orb.NAME, report, orb.params_dict, text, clock())
    return report, text


async def _record[P](
    store: Store,
    strategy: str,
    report: ValidationReport[P],
    to_dict: Callable[[P], dict[str, Any]],
    text: str,
    now: datetime,
) -> None:
    await store.record_trials(
        strategy,
        [
            {
                "params": to_dict(t.params),
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
        strategy,
        params=to_dict(report.chosen) if report.chosen is not None else None,
        passed=report.passed,
        edge_r=report.edge_r,
        report_sv=text,
        at=now,
    )


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
    run = run_orb_validation if sys.argv[1:] == ["orb"] else run_validation
    try:
        _, text = await run(
            market=IbkrMarket(ib, lambda: datetime.now(UTC)),
            store=Store(create_engine(database_url_from_env(env))),
            symbols=load_symbols(Path(env.get("JARVIS_UNIVERSE", str(DEFAULT_UNIVERSE)))),
            rules=settings.validation,
            clock=lambda: datetime.now(UTC),
            costs=CostModel.for_plan(settings.economics.commission_plan),
        )
    finally:
        await broker.disconnect()
    sys.stdout.write(text + "\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(asyncio.run(_main()))
