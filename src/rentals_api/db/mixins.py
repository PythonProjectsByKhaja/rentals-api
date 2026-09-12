"""Column sets shared by several models."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column


class AuditMixin:
    """``created_by`` / ``created_at`` / ``updated_by`` / ``updated_at``.

    Every table in the rentals ER diagram carries these four columns. Declarative
    copies each ``mapped_column`` below onto every model that mixes this in, so
    each table gets its own columns, placed after the model's own.

    The ``*_by`` columns are nullable UUIDs with no foreign key because there is no
    users table yet. Routers fill them from the ``ActorId`` dependency in
    ``api/deps.py``. Once real authentication exists, backfill them, then make
    them NOT NULL and point them at the users table.

    ``updated_at`` is also set on insert, so it always holds the time of the latest
    write. ``onupdate`` is applied by SQLAlchemy, not by a database trigger: it
    adds ``updated_at = now()`` to every UPDATE it emits, so raw SQL bypasses it.
    """

    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, default=None)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
