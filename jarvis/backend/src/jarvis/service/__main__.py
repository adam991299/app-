"""Run one Jarvis service: ``python -m jarvis.service --name risk-engine``."""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence

import uvicorn

from jarvis.config import ConfigError, load_settings_from_env
from jarvis.service.app import create_app
from jarvis.service.logging import configure_logging
from jarvis.service.names import ServiceName

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
        load_settings_from_env()
    except ConfigError:
        logger.exception("refusing to start: configuration is invalid")
        return 1

    logger.info("starting service")
    uvicorn.run(create_app(service), host=args.host, port=args.port, log_config=None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
