"""Shared test fixtures.

Design notes, because several of these choices are non-obvious:

* **No ``event_loop`` fixture.** pytest-asyncio 1.0 removed it. Loop scope is
  configured in pyproject.toml instead, and BOTH
  ``asyncio_default_fixture_loop_scope`` and ``asyncio_default_test_loop_scope``
  must be ``session`` -- otherwise the session-scoped engine and the
  function-scoped test end up in different loops and asyncpg raises
  "got Future attached to a different loop".

* **Tests run against a real database**, not SQLite. SQLite silently diverges on
  JSONB/ARRAY/UUID, does not enforce foreign keys by default (so integrity
  tests pass vacuously), and its crippled ALTER TABLE would force batch mode --
  meaning the migration path you ship to production would never be executed by
  the suite.

* **Each test runs inside a transaction that is rolled back.** The schema is
  built once per session by running the real migration chain, so migrations are
  exercised on every run.

* If the database is unreachable, database-backed tests **skip** with a clear
  message rather than erroring, so ``uv run poe test`` works on a fresh clone
  with nothing running.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from rentals_api.core.config import get_settings
from rentals_api.db.session import get_db
from rentals_api.main import app

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_INI = PROJECT_ROOT / "alembic.ini"


@pytest.fixture(scope="session")
def db_url() -> str:
    """The database the suite runs against.

    Defaults to a dedicated ``*_test`` database so a test run can never touch
    development data.

    This fixture is the ONLY seam between the suite and its database. To use
    testcontainers instead, replace the body with::

        from testcontainers.postgres import PostgresContainer

        with PostgresContainer("postgres:17-alpine", driver="asyncpg") as pg:
            yield pg.get_connection_url()

    Nothing else in the chain changes.
    """
    override = os.environ.get("TEST_DATABASE_URL")
    if override:
        return override

    settings = get_settings()
    url = settings.sqlalchemy_url.set(database=f"{settings.postgres_db}_test")
    return url.render_as_string(hide_password=False)


def _upgrade_to_head(sync_connection: Connection) -> None:
    """Run the real migration chain on an existing connection.

    Passing the connection through ``config.attributes`` is what makes this
    possible: ``alembic/env.py`` reuses it instead of calling ``asyncio.run()``,
    which would fail from inside an already-running event loop.
    """
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    cfg.attributes["connection"] = sync_connection
    command.upgrade(cfg, "head")


@pytest_asyncio.fixture(scope="session")
async def engine(db_url: str) -> AsyncIterator[AsyncEngine]:
    """Session-wide engine with the schema migrated to head.

    NullPool keeps connections from outliving the loop, which avoids spurious
    ConnectionResetError from Proactor transports on Windows at shutdown.
    """
    eng = create_async_engine(db_url, poolclass=NullPool)

    try:
        async with eng.connect():
            pass
    except Exception as exc:
        await eng.dispose()
        pytest.skip(
            "Database-backed tests skipped: cannot reach the test database.\n"
            f"  url:   {db_url}\n"
            f"  error: {type(exc).__name__}: {exc}\n"
            "  fix:   docker compose up -d db",
        )

    async with eng.begin() as conn:
        await conn.run_sync(_upgrade_to_head)

    yield eng

    # Dispose explicitly rather than relying on __del__.
    await eng.dispose()


@pytest_asyncio.fixture
async def connection(engine: AsyncEngine) -> AsyncIterator[AsyncConnection]:
    """A connection wrapped in a transaction that is always rolled back.

    This is the isolation boundary: whatever a test writes disappears, with no
    need to recreate the schema between tests.
    """
    async with engine.connect() as conn:
        transaction = await conn.begin()
        try:
            yield conn
        finally:
            await transaction.rollback()


@pytest_asyncio.fixture
async def session(connection: AsyncConnection) -> AsyncIterator[AsyncSession]:
    """A session joined to the outer transaction.

    ``join_transaction_mode="create_savepoint"`` means a ``session.commit()`` in
    application code commits a SAVEPOINT, never the outer transaction -- so real
    commit behavior is exercised while the test still rolls back cleanly.

    SQLAlchemy 2.0 handles this natively; the old ``after_transaction_end``
    event-listener workaround is no longer needed.
    """
    async with AsyncSession(
        bind=connection,
        join_transaction_mode="create_savepoint",
        expire_on_commit=False,
    ) as async_session:
        yield async_session


@pytest_asyncio.fixture
async def client(session: AsyncSession) -> AsyncIterator[AsyncClient]:
    """An HTTP client bound to the app, sharing the test's transaction.

    Because the app's ``get_db`` is overridden with the same session, requests
    made through this client see the test's uncommitted rows and vice versa.
    """

    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_db] = _override_get_db

    # httpx 0.28 removed the AsyncClient(app=...) shortcut; ASGITransport is the
    # supported path. Note it does NOT run lifespan events -- which is why the
    # engine is created at import time in db/session.py rather than on startup.
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def anon_client() -> AsyncIterator[AsyncClient]:
    """A client with no database wiring, for endpoints that touch no DB."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client


def pytest_configure(config: Any) -> None:
    config.addinivalue_line("markers", "integration: exercises a real database")
