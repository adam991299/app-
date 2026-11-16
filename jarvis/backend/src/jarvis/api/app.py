"""The app's HTTP API (§2). Caddy forwards /api/* here with the prefix removed.

Read-only for now: every endpoint only reads stored state. Endpoints that change
anything (pause, kill switch) come with passkey login in Fas 6/7 (§10).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from fastapi import FastAPI, Query

from jarvis.api.auth import AuthConfig, create_auth_router
from jarvis.api.schemas import (
    DaytradingOut,
    EconomicsOut,
    PortfolioOut,
    StatusOut,
    TodayOut,
    TradesOut,
)
from jarvis.api.views import Views
from jarvis.config.settings import Settings
from jarvis.service.app import create_app
from jarvis.service.names import ServiceName
from jarvis.store.auth import AuthStore
from jarvis.store.repo import Store


def create_api_app(
    store: Store,
    settings: Settings,
    clock: Callable[[], datetime],
    auth: tuple[AuthStore, AuthConfig] | None = None,
) -> FastAPI:
    app = create_app(ServiceName.API)
    if auth is not None:
        app.include_router(create_auth_router(auth[0], store, auth[1], clock))
    views = Views(store, settings, clock)

    @app.get("/status")
    async def status() -> StatusOut:
        return await views.status()

    @app.get("/portfolio")
    async def portfolio() -> PortfolioOut:
        return await views.portfolio()

    @app.get("/trades")
    async def trades(limit: int = Query(default=10, ge=1, le=100)) -> TradesOut:
        return await views.trades(limit)

    @app.get("/today")
    async def today() -> TodayOut:
        return await views.today()

    @app.get("/economics")
    async def economics() -> EconomicsOut:
        return await views.economics()

    @app.get("/daytrading")
    async def daytrading() -> DaytradingOut:
        return await views.daytrading()

    return app
