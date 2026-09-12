"""ORM models for the Property slice: ``properties``, ``property_images`` and
the ``property_amenities`` join table.

Relationships here are READ-ONLY (``viewonly=True``). They exist so a property can
be loaded together with its location, images and amenities; every write goes
through plain foreign-key columns and explicit rows in ``service.py``. That keeps
two things simple:

* No ORM cascade configuration. Deleting a property relies on
  ``ON DELETE CASCADE`` in the database to remove its images and amenity links.
* ``lazy="raise"``. Under asyncio an implicit lazy load is an error anyway
  (MissingGreenlet). With ``raise``, a forgotten ``selectinload`` fails at once
  with a message naming the relationship, not a confusing greenlet error.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import CheckConstraint, Date, Enum, ForeignKey, Integer, Numeric, String, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from rentals_api.amenities.models import Amenity
from rentals_api.db.base_class import Base
from rentals_api.db.mixins import AuditMixin
from rentals_api.locations.models import Location


class PropertyType(StrEnum):
    APARTMENT = "apartment"
    INDEPENDENT_HOUSE = "independent_house"
    VILLA = "villa"
    STUDIO = "studio"


class Furnishing(StrEnum):
    UNFURNISHED = "unfurnished"
    SEMI_FURNISHED = "semi_furnished"
    FULLY_FURNISHED = "fully_furnished"


class PropertyStatus(StrEnum):
    AVAILABLE = "available"
    RENTED = "rented"
    INACTIVE = "inactive"


def _pg_enum(enum_class: type[StrEnum], name: str) -> Enum:
    """A native PostgreSQL enum type that stores the member VALUES.

    Without ``values_callable`` SQLAlchemy stores member NAMES ("SEMI_FURNISHED")
    instead of values ("semi_furnished"). Routing all three enums through this
    helper means that trap cannot be forgotten on one of them.
    """
    return Enum(
        enum_class,
        name=name,
        values_callable=lambda members: [member.value for member in members],
    )


# Money columns: up to 9,999,999,999.99. Numeric maps to Decimal, never float.
Money = Numeric(12, 2)


class Property(AuditMixin, Base):
    __tablename__ = "properties"
    # Named CHECK constraints become "ck_properties_<name>" via NAMING_CONVENTION.
    # The API validates the same rules; these guard every other writer.
    __table_args__ = (
        CheckConstraint("bedrooms >= 0", name="bedrooms_non_negative"),
        CheckConstraint("monthly_rent >= 0", name="monthly_rent_non_negative"),
        CheckConstraint("security_deposit >= 0", name="security_deposit_non_negative"),
        CheckConstraint("carpet_area_sqft > 0", name="carpet_area_sqft_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    location_id: Mapped[uuid.UUID] = mapped_column(
        # RESTRICT: a location with properties cannot be deleted out from under them.
        ForeignKey("locations.id", ondelete="RESTRICT"),
        # PostgreSQL does not index foreign-key columns automatically.
        index=True,
    )
    title: Mapped[str] = mapped_column(String(200))
    property_type: Mapped[PropertyType] = mapped_column(_pg_enum(PropertyType, "property_type"))
    furnishing: Mapped[Furnishing] = mapped_column(_pg_enum(Furnishing, "furnishing"))
    status: Mapped[PropertyStatus] = mapped_column(
        # The ER diagram calls this type "status"; "property_status" avoids
        # colliding with any other status enum added later (bookings, payments).
        _pg_enum(PropertyStatus, "property_status"),
        # A Python-side default, deliberately not server_default: server defaults
        # on enum columns are a source of false drift with compare_server_default.
        default=PropertyStatus.AVAILABLE,
    )
    bedrooms: Mapped[int] = mapped_column(Integer)
    monthly_rent: Mapped[Decimal] = mapped_column(Money)
    security_deposit: Mapped[Decimal] = mapped_column(Money)
    carpet_area_sqft: Mapped[int | None] = mapped_column(Integer, default=None)
    available_from: Mapped[date] = mapped_column(Date)

    location: Mapped[Location] = relationship(viewonly=True, lazy="raise")
    images: Mapped[list[PropertyImage]] = relationship(
        viewonly=True,
        lazy="raise",
        # A lambda because PropertyImage is defined further down this module;
        # SQLAlchemy calls it when mappers are configured. id breaks ties.
        order_by=lambda: [PropertyImage.position, PropertyImage.id],
    )
    amenities: Mapped[list[Amenity]] = relationship(
        secondary="property_amenities",
        viewonly=True,
        lazy="raise",
        order_by=Amenity.name,
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Property id={self.id!r} title={self.title!r}>"


class PropertyImage(AuditMixin, Base):
    __tablename__ = "property_images"
    __table_args__ = (CheckConstraint("position >= 0", name="position_non_negative"),)

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    property_id: Mapped[uuid.UUID] = mapped_column(
        # CASCADE: images belong to their property and go with it.
        ForeignKey("properties.id", ondelete="CASCADE"),
        index=True,
    )
    # 2083 matches the max_length pydantic.HttpUrl enforces on input.
    url: Mapped[str] = mapped_column(String(2083))
    position: Mapped[int] = mapped_column(Integer, default=0)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<PropertyImage id={self.id!r} position={self.position!r}>"


class PropertyAmenity(AuditMixin, Base):
    """One row per (property, amenity) pair.

    A mapped class rather than a bare ``Table`` because the ER diagram gives the
    link its own audit columns: who attached the amenity, and when.
    """

    __tablename__ = "property_amenities"

    property_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("properties.id", ondelete="CASCADE"),
        primary_key=True,
    )
    amenity_id: Mapped[uuid.UUID] = mapped_column(
        # RESTRICT: an amenity still in use cannot be deleted from the catalogue.
        ForeignKey("amenities.id", ondelete="RESTRICT"),
        primary_key=True,
        # The composite primary key already indexes property_id, its leading
        # column. Lookups by amenity, including the RESTRICT check when an
        # amenity is deleted, need their own index.
        index=True,
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<PropertyAmenity property_id={self.property_id!r} amenity_id={self.amenity_id!r}>"
