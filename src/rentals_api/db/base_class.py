"""The declarative base and its constraint naming convention."""

from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# Deterministic names for every constraint and index.
#
# Without this, the database assigns its own names, and a later migration that
# needs to drop a constraint has nothing stable to name. Alembic autogenerate
# also produces cleaner diffs.
#
# IMPORTANT: this must be in place BEFORE the first migration is generated.
# Retrofitting it means every constraint in the initial migration has the wrong
# name, and autogenerate will propose dropping and recreating all of them.
#
# `column_0_N_name` (all columns) is used instead of `column_0_name` (the first
# only), so that two composite indexes on the same table that happen to share a
# leading column do not collide.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

# Two caveats worth knowing:
#   * PostgreSQL silently truncates identifiers at 63 characters, which later
#     surfaces as phantom autogenerate drift on long table+column combinations.
#   * The "ck" pattern raises at DDL time for an UNNAMED CheckConstraint. Native
#     Boolean/Enum are fine; sa.Enum(native_enum=False) will bite you.


class Base(DeclarativeBase):
    """Base class for every ORM model."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
