"""Bring the database schema up to date (Alembic). Safe to run on every start."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config

ALEMBIC_INI = Path(__file__).resolve().parents[3] / "alembic.ini"


def migrate(url: str, revision: str = "head") -> None:
    config = Config(str(ALEMBIC_INI))
    config.attributes["database_url"] = url
    command.upgrade(config, revision)
