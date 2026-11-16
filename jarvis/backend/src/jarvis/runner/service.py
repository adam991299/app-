"""Builds the execution-engine service: IB Gateway, market data, execution, clock check
and the runner loop, started and stopped with the web server that reports its health."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

import yaml
from fastapi import FastAPI
from ib_async import IB

from jarvis.broker.ibkr import IbkrBroker, IbkrSettings
from jarvis.config import ConfigError, Settings
from jarvis.domain import AssetClass, Instrument
from jarvis.execution.alerts import AlertLevel, Alerts
from jarvis.execution.engine import ExecutionEngine
from jarvis.marketdata.ibkr import IbkrMarket
from jarvis.markets.calendar import Exchange, session_at
from jarvis.notify.email import EmailAlerts, FanOut, smtp_settings_from_env
from jarvis.runner.clock import ClockMonitor, ntp_measure
from jarvis.runner.daytrade import DayTrader
from jarvis.runner.loop import Runner
from jarvis.service.app import create_app
from jarvis.service.names import ServiceName
from jarvis.store.db import create_engine, database_url_from_env
from jarvis.store.migrate import migrate
from jarvis.store.repo import Store

logger = logging.getLogger(__name__)
DEFAULT_UNIVERSE = Path("/app/config/universe_us.yaml")


class LogAlerts:
    """Every alert is logged; e-mail is added when it is configured (Web Push: Fas 6)."""

    async def send(self, level: AlertLevel, message_sv: str) -> None:
        log = logger.critical if level is AlertLevel.CRITICAL else logger.warning
        log("ALERT: %s", message_sv)


def _report_unexpected_end(task: asyncio.Task[None]) -> None:
    if not task.cancelled() and task.exception() is not None:
        logger.critical("the trading loop stopped unexpectedly", exc_info=task.exception())


def ibkr_settings_from_env(env: Mapping[str, str]) -> IbkrSettings:
    account = env.get("JARVIS_IBKR_ACCOUNT", "")
    if not account:
        raise ConfigError("JARVIS_IBKR_ACCOUNT is not set (the paper account id, DU...)")
    try:
        port = int(env.get("JARVIS_IBKR_PORT", "4004"))
        client_id = int(env.get("JARVIS_IBKR_CLIENT_ID", "1"))
    except ValueError as exc:
        raise ConfigError("JARVIS_IBKR_PORT and JARVIS_IBKR_CLIENT_ID must be numbers") from exc
    return IbkrSettings(
        host=env.get("JARVIS_IBKR_HOST", "ib-gateway"),
        port=port,
        client_id=client_id,
        account=account,
    )


def load_symbols(path: Path) -> list[str]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConfigError(f"cannot read universe file {path}: {exc}") from exc
    symbols = data.get("symbols") if isinstance(data, dict) else None
    if not isinstance(symbols, list) or not all(isinstance(s, str) and s for s in symbols):
        raise ConfigError(f"universe file {path} must contain a list 'symbols'")
    return symbols


def create_execution_app(settings: Settings, env: Mapping[str, str]) -> FastAPI:
    url = database_url_from_env(env)
    ibkr = ibkr_settings_from_env(env)
    symbols = load_symbols(Path(env.get("JARVIS_UNIVERSE", str(DEFAULT_UNIVERSE))))
    smtp = smtp_settings_from_env(env)
    alerts: Alerts = LogAlerts() if smtp is None else FanOut(LogAlerts(), EmailAlerts(smtp))
    migrate(url)
    app = create_app(ServiceName.EXECUTION)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        def clock() -> datetime:
            return datetime.now(UTC)

        ib = IB()
        store = Store(create_engine(url))
        market = IbkrMarket(ib, clock)
        monitor = ClockMonitor(ntp_measure())
        instruments: dict[str, Instrument] = {}
        broker = IbkrBroker(ib, ibkr)
        engine = ExecutionEngine(
            broker=broker,
            store=store,
            risk=settings.risk,
            instruments=instruments,
            quotes=market.quote,
            sessions=lambda _i, now: session_at(Exchange.NYSE, now),
            clock=clock,
            clock_drift=monitor.drift,
            alerts=alerts,
        )
        runner = Runner(
            broker=broker,
            engine=engine,
            market=market,
            store=store,
            instruments=instruments,
            symbols=symbols,
            clock=clock,
            before_tick=monitor.refresh,
            risk=settings.risk,
            index_fund=Instrument(
                settings.economics.index_fund_symbol, "SMART", "USD", AssetClass.ETF, "index"
            ),
            day_trader=DayTrader(
                broker=broker,
                engine=engine,
                market=market,
                store=store,
                instruments=instruments,
                clock=clock,
                risk=settings.risk,
            ),
        )
        stop = asyncio.Event()
        task = asyncio.create_task(runner.run(stop))
        task.add_done_callback(_report_unexpected_end)
        try:
            yield
        finally:
            stop.set()
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
            ib.disconnect()

    app.router.lifespan_context = lifespan
    return app
