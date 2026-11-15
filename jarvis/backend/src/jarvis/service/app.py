"""The HTTP surface every Jarvis service exposes: a health endpoint."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import FastAPI
from pydantic import BaseModel

from jarvis import __version__
from jarvis.service.names import ServiceName


class Health(BaseModel):
    service: ServiceName
    status: str
    version: str
    time: datetime


def create_app(service: ServiceName) -> FastAPI:
    app = FastAPI(
        title=f"Jarvis {service.value}",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    @app.get("/healthz")
    def healthz() -> Health:
        return Health(service=service, status="ok", version=__version__, time=datetime.now(UTC))

    return app
