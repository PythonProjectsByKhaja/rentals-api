"""ORM model for the Location slice.

There is deliberately no ``properties`` relationship here: this slice does not
need to know that properties exist. The link is the foreign key on
``properties.location_id``, which is ``ON DELETE RESTRICT``, so a location that
still has properties cannot be deleted (see ``service.delete_location``).
"""

from __future__ import annotations

import uuid

from sqlalchemy import String, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from rentals_api.db.base_class import Base
from rentals_api.db.mixins import AuditMixin


class Location(AuditMixin, Base):
    __tablename__ = "locations"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    city: Mapped[str] = mapped_column(String(100))
    locality: Mapped[str] = mapped_column(String(200))
    state: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(String(2000), default=None)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Location id={self.id!r} locality={self.locality!r} city={self.city!r}>"
