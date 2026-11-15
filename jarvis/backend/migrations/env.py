"""Alembic environment. The database URL comes from JARVIS_DATABASE_URL (never from a file)."""

from __future__ import annotations

import asyncio

from alembic import context
from sqlalchemy.engine import Connection

from jarvis.store.db import create_engine, database_url_from_env
from jarvis.store.tables import Base


def _run(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()


async def _run_async() -> None:
    url = context.config.attributes.get("database_url") or database_url_from_env()
    engine = create_engine(url)
    async with engine.connect() as connection:
        await connection.run_sync(_run)
        await connection.commit()
    await engine.dispose()


asyncio.run(_run_async())
