"""Pydantic v2 schemas for the ``Item`` slice.

These are the API's contract. Keeping them separate from the ORM model means
the wire format can change without touching the database, and vice versa.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)


class ItemUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)


class ItemRead(BaseModel):
    # from_attributes lets FastAPI serialize the ORM object directly.
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    created_at: datetime
