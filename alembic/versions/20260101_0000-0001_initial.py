"""initial

Revision ID: 0001_initial
Revises:
Create Date: 2026-01-01 00:00:00.000000+00:00

Hand-written to match src/rentals_api/items/models.py exactly, including
the constraint names produced by NAMING_CONVENTION in db/base_class.py.

`tests/test_migrations.py` asserts that this migration and the ORM metadata
agree, so if you edit the model without adding a migration, the suite fails.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "items",
        sa.Column(
            "id",
            sa.Uuid(),
            # Built into PostgreSQL 13+; the pgcrypto extension is not required.
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.String(length=2000), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_items")),
    )
    op.create_index(op.f("ix_items_name"), "items", ["name"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_items_name"), table_name="items")
    op.drop_table("items")
