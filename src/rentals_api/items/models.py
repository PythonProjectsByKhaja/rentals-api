"""ORM model for the example ``Item`` slice.

Models hold shape only -- columns, relationships, table args. Business logic
lives in ``service.py``.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column

from rentals_api.db.base_class import Base


class Item(Base):
    __tablename__ = "items"

    id: Mapped[uuid.UUID] = mapped_column(
        # sa.Uuid is backend-agnostic in SQLAlchemy 2.0: native uuid on
        # PostgreSQL, CHAR(32) elsewhere.
        Uuid,
        primary_key=True,
        # gen_random_uuid() is built into PostgreSQL 13+; no pgcrypto needed.
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(String(200), index=True)
    description: Mapped[str | None] = mapped_column(String(2000), default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Item id={self.id!r} name={self.name!r}>"
