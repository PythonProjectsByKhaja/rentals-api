"""Pydantic v2 schemas for the Property slice.

Money is ``Decimal`` end to end: the API accepts ``25000``, ``25000.5`` or
``"25000.50"``, and always returns a string such as ``"25000.00"``. Pydantic
serializes ``Decimal`` to a JSON string so no precision is lost to floats.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from rentals_api.amenities.schemas import AmenitySummary
from rentals_api.locations.schemas import LocationSummary
from rentals_api.properties.models import Furnishing, PropertyStatus, PropertyType

# Mirrors Numeric(12, 2) on the money columns.
Money = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]
Bedrooms = Annotated[int, Field(ge=0, le=50)]
CarpetArea = Annotated[int, Field(gt=0)]
Title = Annotated[str, Field(min_length=1, max_length=200)]


def _reject_null(value: object) -> object:
    """Shared by the PATCH schemas below.

    Omitting a field leaves it unchanged; an explicit null is rejected with a 422,
    because these columns are NOT NULL and the database would otherwise fail with
    a 500. Validators only run on values the client actually sent, never on the
    ``None`` default, which is what makes this work.
    """
    if value is None:
        raise ValueError("must not be null; omit the field to leave it unchanged")
    return value


# --- properties --------------------------------------------------------------


class PropertyCreate(BaseModel):
    location_id: uuid.UUID
    title: Title
    property_type: PropertyType
    furnishing: Furnishing
    status: PropertyStatus = PropertyStatus.AVAILABLE
    bedrooms: Bedrooms
    monthly_rent: Money
    security_deposit: Money
    carpet_area_sqft: CarpetArea | None = None
    available_from: date
    # A set, so a repeated id cannot produce a duplicate join row.
    amenity_ids: set[uuid.UUID] = Field(default_factory=set)


class PropertyUpdate(BaseModel):
    """PATCH body. Amenities are changed through ``PUT .../amenities`` instead."""

    location_id: uuid.UUID | None = None
    title: Title | None = None
    property_type: PropertyType | None = None
    furnishing: Furnishing | None = None
    status: PropertyStatus | None = None
    bedrooms: Bedrooms | None = None
    monthly_rent: Money | None = None
    security_deposit: Money | None = None
    # Nullable in the database, so null is a legitimate way to clear it.
    carpet_area_sqft: CarpetArea | None = None
    available_from: date | None = None

    @field_validator(
        "location_id",
        "title",
        "property_type",
        "furnishing",
        "status",
        "bedrooms",
        "monthly_rent",
        "security_deposit",
        "available_from",
        mode="before",
    )
    @classmethod
    def reject_null(cls, value: object) -> object:
        return _reject_null(value)


class PropertyQuery(BaseModel):
    """Query string for ``GET /properties``. Every filter is optional; they combine with AND.

    Pagination lives in here too, rather than in separate ``limit``/``offset``
    parameters, because FastAPI only expands a model into query parameters when
    it is the endpoint's ONLY query parameter.
    """

    location_id: uuid.UUID | None = None
    city: str | None = Field(default=None, min_length=1, max_length=100)
    property_type: PropertyType | None = None
    furnishing: Furnishing | None = None
    status: PropertyStatus | None = None
    min_bedrooms: Bedrooms | None = None
    min_rent: Money | None = None
    max_rent: Money | None = None
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


# --- images ------------------------------------------------------------------


class PropertyImageCreate(BaseModel):
    url: HttpUrl
    position: int = Field(default=0, ge=0)


class PropertyImageUpdate(BaseModel):
    url: HttpUrl | None = None
    position: int | None = Field(default=None, ge=0)

    @field_validator("url", "position", mode="before")
    @classmethod
    def reject_null(cls, value: object) -> object:
        return _reject_null(value)


class PropertyImageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    url: str
    position: int


# --- amenities ---------------------------------------------------------------


class PropertyAmenitiesUpdate(BaseModel):
    """PUT body: the complete set of amenities the property should have."""

    amenity_ids: set[uuid.UUID]


# --- read model --------------------------------------------------------------


class PropertyRead(BaseModel):
    """A property with its location, images and amenities embedded.

    Built straight from the ORM object, whose relationships the service always
    loads, so serializing it never triggers a lazy load.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    property_type: PropertyType
    furnishing: Furnishing
    status: PropertyStatus
    bedrooms: int
    monthly_rent: Decimal
    security_deposit: Decimal
    carpet_area_sqft: int | None
    available_from: date
    location: LocationSummary
    images: list[PropertyImageRead]
    amenities: list[AmenitySummary]
    created_by: uuid.UUID | None
    created_at: datetime
    updated_by: uuid.UUID | None
    updated_at: datetime
