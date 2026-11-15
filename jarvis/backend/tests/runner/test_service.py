from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

import pytest

from jarvis.config import ConfigError, Settings
from jarvis.execution.alerts import AlertLevel
from jarvis.runner import service
from jarvis.runner.service import (
    LogAlerts,
    create_execution_app,
    ibkr_settings_from_env,
    load_symbols,
)

UNIVERSE = Path(__file__).parents[3] / "config" / "universe_us.yaml"


def test_ibkr_settings_need_the_paper_account() -> None:
    with pytest.raises(ConfigError, match="JARVIS_IBKR_ACCOUNT"):
        ibkr_settings_from_env({})
    with pytest.raises(ConfigError, match="numbers"):
        ibkr_settings_from_env({"JARVIS_IBKR_ACCOUNT": "DU1", "JARVIS_IBKR_PORT": "x"})
    settings = ibkr_settings_from_env({"JARVIS_IBKR_ACCOUNT": "DU1"})
    assert (settings.host, settings.port, settings.client_id) == ("ib-gateway", 4004, 1)


def test_shipped_universe_loads(tmp_path: Path) -> None:
    symbols = load_symbols(UNIVERSE)
    assert len(symbols) == 20
    assert len(set(symbols)) == 20
    with pytest.raises(ConfigError, match="cannot read"):
        load_symbols(tmp_path / "missing.yaml")
    bad = tmp_path / "bad.yaml"
    bad.write_text("symbols: [AAPL, 3]\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="list 'symbols'"):
        load_symbols(bad)
    bad.write_text("- AAPL\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="list 'symbols'"):
        load_symbols(bad)


async def test_alerts_are_logged_until_the_notifier_exists(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING):
        await LogAlerts().send(AlertLevel.CRITICAL, "Stoppad.")
        await LogAlerts().send(AlertLevel.WARNING, "Varning.")
    assert [r.levelname for r in caplog.records] == ["CRITICAL", "WARNING"]


class GatewayDown:
    """Stands in for ib_async.IB: the gateway never answers."""

    client: Any = None

    def isConnected(self) -> bool:  # noqa: N802
        return False

    async def connectAsync(self, *args: Any, **kwargs: Any) -> None:  # noqa: N802
        raise ConnectionRefusedError("no gateway")

    def disconnect(self) -> None:
        return None


def test_service_starts_the_runner_and_stops_it_cleanly(
    database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Built like in production: migrations first (no event loop), then the server's loop."""
    monkeypatch.setattr(service, "IB", GatewayDown)
    env = {
        "JARVIS_DATABASE_URL": database_url,
        "JARVIS_IBKR_ACCOUNT": "DU1",
        "JARVIS_UNIVERSE": str(UNIVERSE),
    }
    app = create_execution_app(Settings(), env)

    async def serve_briefly() -> None:
        async with app.router.lifespan_context(app):
            await asyncio.sleep(0.05)  # the runner is retrying the connection

    asyncio.run(serve_briefly())
    routes = {getattr(r, "path", "") for r in app.routes}
    assert "/healthz" in routes


def test_service_with_email_alerts_configured(
    database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(service, "IB", GatewayDown)
    env = {
        "JARVIS_DATABASE_URL": database_url,
        "JARVIS_IBKR_ACCOUNT": "DU1",
        "JARVIS_UNIVERSE": str(UNIVERSE),
        "JARVIS_SMTP_HOST": "smtp.gmail.com",
        "JARVIS_SMTP_USER": "jarvis@example.com",
        "JARVIS_SMTP_PASSWORD": "x",
        "JARVIS_ALERT_EMAIL": "adam@example.com",
    }
    assert create_execution_app(Settings(), env) is not None
    with pytest.raises(ConfigError, match="half configured"):
        create_execution_app(Settings(), {k: v for k, v in env.items() if k != "JARVIS_SMTP_HOST"})
