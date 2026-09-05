"""Alembic environment, wired for an async engine.

Three things here are load-bearing and easy to get wrong; each is explained at
the point where it matters:

1. The URL is injected into a plain dict, never via ``set_main_option``.
2. The password is rendered with ``hide_password=False``.
3. ``run_migrations_online`` honors a caller-supplied connection, which is what
   lets the test suite run the real migration chain.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig
from typing import Any

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from rentals_api.core.config import get_settings

# Importing this module registers every model on Base.metadata. It is the whole
# reason db/base.py exists -- see the note there before adding a model.
from rentals_api.db.base import Base

config = context.config

# Only configure logging for real CLI invocations. When pytest calls
# command.upgrade() programmatically it passes a connection, and running
# fileConfig() there would tear down pytest's log capture.
if config.config_file_name is not None and "connection" not in config.attributes:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# A sqlalchemy.engine.URL object, not a string.
DB_URL = get_settings().sqlalchemy_url


def _skip_empty_migration(
    context_: Any,
    revision: Any,
    directives: list[Any],
) -> None:
    """Write no file when ``--autogenerate`` finds nothing to do.

    This turns "no output" into the success signal for the drift check in CI and
    in tests, instead of leaving a trail of empty revision files.
    """
    if getattr(config.cmd_opts, "autogenerate", False) and directives[0].upgrade_ops.is_empty():
        directives[:] = []


def _configure(**kwargs: Any) -> None:
    context.configure(
        target_metadata=target_metadata,
        # Default since Alembic 1.12; stated explicitly as documentation.
        compare_type=True,
        # PostgreSQL performs a genuine server-side comparison here, so false
        # positives are rare and real drift gets caught.
        compare_server_default=True,
        include_schemas=False,
        # Batch mode is a SQLite workaround for its crippled ALTER TABLE.
        render_as_batch=False,
        process_revision_directives=_skip_empty_migration,
        **kwargs,
    )


def do_run_migrations(connection: Connection) -> None:
    """Run migrations against a live *synchronous* Connection.

    Under async this is reached via ``connection.run_sync(...)``, which supplies
    the greenlet-bridged sync facade Alembic expects.
    """
    _configure(connection=connection)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    section = config.get_section(config.config_ini_section, {})

    # Inject into the plain dict returned by get_section(), NOT via
    # config.set_main_option(). set_main_option writes through ConfigParser,
    # which interprets '%' as interpolation syntax -- so a percent-encoded
    # password raises InterpolationSyntaxError. A dict does no interpolation.
    #
    # render_as_string(hide_password=False) is mandatory: plain str(url) masks
    # the password as '***', producing a URL that cannot authenticate.
    section["sqlalchemy.url"] = DB_URL.render_as_string(hide_password=False)

    connectable = async_engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry point for online mode.

    When a caller (the pytest fixture) puts a Connection in
    ``config.attributes``, reuse it. Without this branch a programmatic
    ``command.upgrade()`` from inside a running event loop would hit
    ``asyncio.run()`` and raise "cannot be called from a running event loop".
    """
    external_connection = config.attributes.get("connection")
    if external_connection is not None:
        do_run_migrations(external_connection)
    else:
        asyncio.run(run_async_migrations())


def run_migrations_offline() -> None:
    """Emit SQL to stdout instead of executing it (``alembic upgrade --sql``)."""
    _configure(
        url=DB_URL.render_as_string(hide_password=False),
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
