"""Pydantic v2 schemas for the Location slice."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LocationCreate(BaseModel):
    city: str = Field(min_length=1, max_length=100)
    locality: str = Field(min_length=1, max_length=200)
    state: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)


class LocationUpdate(BaseModel):
    city: str | None = Field(default=None, min_length=1, max_length=100)
    locality: str | None = Field(default=None, min_length=1, max_length=200)
    state: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("city", "locality", "state", mode="before")
    @classmethod
    def reject_null(cls, value: object) -> object:
        """Omitting a field leaves it unchanged; an explicit null is rejected.

        These columns are NOT NULL, so without this check ``{"city": null}``
        would get past validation and fail in the database as a 500. Validators
        only run on values the client actually sent, never on the ``None``
        default, which is what makes this work.
        """
        if value is None:
            raise ValueError("must not be null; omit the field to leave it unchanged")
        return value


class LocationSummary(BaseModel):
    """The compact form embedded in each property."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    city: str
    locality: str
    state: str


class LocationRead(LocationSummary):
    description: str | None
    created_by: uuid.UUID | None
    created_at: datetime
    updated_by: uuid.UUID | None
    updated_at: datetime
