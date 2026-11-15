"""A real PostgreSQL for tests that need the store: one server per test session, a freshly migrated
database per test. Fails loudly (never skips) if PostgreSQL is not available.

By default the tests start their own server (as in CI). PostgreSQL refuses to run as
root, so where tests run as root, start a server as another user and point the tests at
it with JARVIS_TEST_POSTGRES=host:port (user ``postgres``, trust auth)."""

from __future__ import annotations

import glob
import itertools
import os
import shutil
from collections.abc import AsyncIterator, Callable, Iterator

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from pytest_postgresql import factories
from pytest_postgresql.executors.noop import NoopExecutor
from pytest_postgresql.executors.proc import PostgreSQLExecutor
from sqlalchemy.ext.asyncio import AsyncEngine

from jarvis.store.db import create_engine
from jarvis.store.repo import Store

ALEMBIC_INI = __file__.rsplit("/tests/", 1)[0] + "/alembic.ini"


def _pg_ctl() -> str:
    found = shutil.which("pg_ctl") or next(
        iter(sorted(glob.glob("/usr/lib/postgresql/*/bin/pg_ctl"), reverse=True)), None
    )
    if found is None:
        raise RuntimeError("PostgreSQL (pg_ctl) is required for the store tests")
    return found


_external = os.environ.get("JARVIS_TEST_POSTGRES")
postgresql_server: Callable[..., Iterator[PostgreSQLExecutor | NoopExecutor]]
if _external:
    _host, _, _port = _external.partition(":")
    postgresql_server = factories.postgresql_noproc(host=_host, port=int(_port), user="postgres")
else:
    postgresql_server = factories.postgresql_proc(executable=_pg_ctl(), port=None)
_counter = itertools.count()


def migrate(url: str, revision: str = "head") -> None:
    config = Config(ALEMBIC_INI)
    config.attributes["database_url"] = url
    command.upgrade(config, revision)


@pytest.fixture
def database_url(postgresql_server: PostgreSQLExecutor | NoopExecutor) -> Iterator[str]:
    name = f"jarvis_test_{next(_counter)}"
    admin = (
        f"host={postgresql_server.host} port={postgresql_server.port} "
        f"user={postgresql_server.user} dbname=postgres"
    )
    with psycopg.connect(admin, autocommit=True) as conn:
        conn.execute(f'CREATE DATABASE "{name}"')
    url = (
        f"postgresql+asyncpg://{postgresql_server.user}@{postgresql_server.host}:"
        f"{postgresql_server.port}/{name}"
    )
    migrate(url)
    yield url
    with psycopg.connect(admin, autocommit=True) as conn:
        conn.execute(f'DROP DATABASE "{name}" WITH (FORCE)')


@pytest.fixture
async def engine(database_url: str) -> AsyncIterator[AsyncEngine]:
    eng = create_engine(database_url)
    yield eng
    await eng.dispose()


@pytest.fixture
def store(engine: AsyncEngine) -> Store:
    return Store(engine)
