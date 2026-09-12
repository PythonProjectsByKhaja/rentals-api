"""ORM model for the Amenity slice.

Which property has which amenity is recorded in the ``property_amenities`` join
table, which belongs to the properties slice. Its foreign key to this table is
``ON DELETE RESTRICT``, so an amenity that is still assigned to a property
cannot be deleted.
"""

from __future__ import annotations

import uuid

from sqlalchemy import String, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from rentals_api.db.base_class import Base
from rentals_api.db.mixins import AuditMixin


class Amenity(AuditMixin, Base):
    __tablename__ = "amenities"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    # unique=True becomes the constraint "uq_amenities_name" via NAMING_CONVENTION.
    name: Mapped[str] = mapped_column(String(100), unique=True)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Amenity id={self.id!r} name={self.name!r}>"
