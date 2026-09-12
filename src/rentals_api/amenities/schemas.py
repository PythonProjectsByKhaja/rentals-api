"""Pydantic v2 schemas for the Amenity slice."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AmenityCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class AmenityUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)

    @field_validator("name", mode="before")
    @classmethod
    def reject_null(cls, value: object) -> object:
        """Omitting ``name`` leaves it unchanged; null would violate NOT NULL."""
        if value is None:
            raise ValueError("must not be null; omit the field to leave it unchanged")
        return value


class AmenitySummary(BaseModel):
    """The compact form embedded in each property."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str


class AmenityRead(AmenitySummary):
    created_by: uuid.UUID | None
    created_at: datetime
    updated_by: uuid.UUID | None
    updated_at: datetime
