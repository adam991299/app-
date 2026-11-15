"""Run one Jarvis service: ``python -m jarvis.service --name risk-engine``."""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence
from datetime import UTC, datetime

import uvicorn
from fastapi import FastAPI

from jarvis.api.app import create_api_app
from jarvis.config import ConfigError, Settings, load_settings_from_env
from jarvis.service.app import create_app
from jarvis.service.logging import configure_logging
from jarvis.service.names import ServiceName
from jarvis.store.db import DatabaseConfigError, create_engine, database_url_from_env
from jarvis.store.migrate import migrate
from jarvis.store.repo import Store

logger = logging.getLogger("jarvis.service")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a Jarvis backend service")
    parser.add_argument("--name", required=True, choices=[s.value for s in ServiceName])
    parser.add_argument("--host", default="0.0.0.0")  # noqa: S104 - container-internal network only
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)

    service = ServiceName(args.name)
    configure_logging(service.value)
    try:
        settings = load_settings_from_env()
        app = build_app(service, settings)
    except ConfigError:
        logger.exception("refusing to start: configuration is invalid")
        return 1
    except DatabaseConfigError:
        logger.exception("refusing to start: no usable database URL")
        return 1

    logger.info("starting service")
    uvicorn.run(app, host=args.host, port=args.port, log_config=None)
    return 0


def build_app(service: ServiceName, settings: Settings) -> FastAPI:
    """The API serves the app from the database; other services are still health-only."""
    if service is not ServiceName.API:
        return create_app(service)
    url = database_url_from_env()
    migrate(url)
    return create_api_app(Store(create_engine(url)), settings, lambda: datetime.now(UTC))


if __name__ == "__main__":
    sys.exit(main())
