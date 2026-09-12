"""HTTP layer for the Property slice.

Paths, status codes and response models only; logic lives in ``service``.
Images and amenities are addressed through their property, because neither
exists without one.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Query, status

from rentals_api.amenities.models import Amenity
from rentals_api.amenities.schemas import AmenitySummary
from rentals_api.api.deps import ActorId, DbSession
from rentals_api.properties import service
from rentals_api.properties.models import Property, PropertyImage
from rentals_api.properties.schemas import (
    PropertyAmenitiesUpdate,
    PropertyCreate,
    PropertyImageCreate,
    PropertyImageRead,
    PropertyImageUpdate,
    PropertyQuery,
    PropertyRead,
    PropertyUpdate,
)

router = APIRouter(prefix="/properties", tags=["properties"])


@router.get("", response_model=list[PropertyRead])
async def list_properties(
    db: DbSession, query: Annotated[PropertyQuery, Query()]
) -> Sequence[Property]:
    return await service.list_properties(db, query)


@router.post("", response_model=PropertyRead, status_code=status.HTTP_201_CREATED)
async def create_property(payload: PropertyCreate, db: DbSession, actor_id: ActorId) -> Property:
    return await service.create_property(db, payload, actor_id=actor_id)


@router.get("/{property_id}", response_model=PropertyRead)
async def get_property(property_id: uuid.UUID, db: DbSession) -> Property:
    return await service.get_property(db, property_id)


@router.patch("/{property_id}", response_model=PropertyRead)
async def update_property(
    property_id: uuid.UUID, payload: PropertyUpdate, db: DbSession, actor_id: ActorId
) -> Property:
    return await service.update_property(db, property_id, payload, actor_id=actor_id)


@router.delete("/{property_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_property(property_id: uuid.UUID, db: DbSession) -> None:
    await service.delete_property(db, property_id)


@router.put("/{property_id}/amenities", response_model=list[AmenitySummary])
async def set_property_amenities(
    property_id: uuid.UUID, payload: PropertyAmenitiesUpdate, db: DbSession, actor_id: ActorId
) -> list[Amenity]:
    return await service.set_amenities(db, property_id, payload.amenity_ids, actor_id=actor_id)


@router.post(
    "/{property_id}/images",
    response_model=PropertyImageRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_property_image(
    property_id: uuid.UUID, payload: PropertyImageCreate, db: DbSession, actor_id: ActorId
) -> PropertyImage:
    return await service.add_image(db, property_id, payload, actor_id=actor_id)


@router.patch("/{property_id}/images/{image_id}", response_model=PropertyImageRead)
async def update_property_image(
    property_id: uuid.UUID,
    image_id: uuid.UUID,
    payload: PropertyImageUpdate,
    db: DbSession,
    actor_id: ActorId,
) -> PropertyImage:
    return await service.update_image(db, property_id, image_id, payload, actor_id=actor_id)


@router.delete("/{property_id}/images/{image_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_property_image(property_id: uuid.UUID, image_id: uuid.UUID, db: DbSession) -> None:
    await service.delete_image(db, property_id, image_id)
