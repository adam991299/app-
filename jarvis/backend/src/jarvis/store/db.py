"""Database connection. The URL is a secret (it contains the password): environment only."""

from __future__ import annotations

import os
from collections.abc import Mapping

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.ext.asyncio import AsyncSession as AsyncSession

DATABASE_URL_ENV = "JARVIS_DATABASE_URL"


class DatabaseConfigError(Exception):
    """No usable database URL. Jarvis must not start without its store."""


def database_url_from_env(environ: Mapping[str, str] | None = None) -> str:
    env = os.environ if environ is None else environ
    url = env.get(DATABASE_URL_ENV, "")
    if not url.startswith("postgresql+asyncpg://"):
        raise DatabaseConfigError(f"{DATABASE_URL_ENV} must be a postgresql+asyncpg:// URL")
    return url


def create_engine(url: str) -> AsyncEngine:
    """Connections time out instead of hanging (§00.3), and dead ones are replaced."""
    return create_async_engine(
        url,
        pool_pre_ping=True,
        connect_args={"timeout": 10, "command_timeout": 30},
    )


def session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)
