"""The drift test.

Arguably the highest-value test in the project: it compares the ORM metadata
against the schema that the migration chain actually produced. It fails loudly
if someone

* adds a model but forgets to register it in ``db/base.py``, or
* changes a model but forgets to generate a migration, or
* hand-edits a migration so it no longer matches the model.

All three otherwise stay invisible until a deploy.
"""

from __future__ import annotations

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncConnection

from rentals_api.db.base import Base

pytestmark = pytest.mark.integration


async def test_models_match_migrations(connection: AsyncConnection) -> None:
    def _diff(sync_connection: Connection) -> list[object]:
        context = MigrationContext.configure(
            sync_connection,
            opts={"compare_type": True, "compare_server_default": True},
        )
        return compare_metadata(context, Base.metadata)

    differences = await connection.run_sync(_diff)

    assert differences == [], (
        "The ORM models and the migrated schema have drifted.\n"
        "Run: uv run poe revision -m 'describe your change'\n"
        f"Differences: {differences}"
    )
