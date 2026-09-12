"""HTTP layer for the Amenity slice.

Paths, status codes and response models only; logic lives in ``service``.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from fastapi import APIRouter, status

from rentals_api.amenities import service
from rentals_api.amenities.models import Amenity
from rentals_api.amenities.schemas import AmenityCreate, AmenityRead, AmenityUpdate
from rentals_api.api.deps import ActorId, DbSession, PageLimit, PageOffset

router = APIRouter(prefix="/amenities", tags=["amenities"])


@router.get("", response_model=list[AmenityRead])
async def list_amenities(
    db: DbSession, limit: PageLimit = 50, offset: PageOffset = 0
) -> Sequence[Amenity]:
    return await service.list_amenities(db, limit=limit, offset=offset)


@router.post("", response_model=AmenityRead, status_code=status.HTTP_201_CREATED)
async def create_amenity(payload: AmenityCreate, db: DbSession, actor_id: ActorId) -> Amenity:
    return await service.create_amenity(db, payload, actor_id=actor_id)


@router.get("/{amenity_id}", response_model=AmenityRead)
async def get_amenity(amenity_id: uuid.UUID, db: DbSession) -> Amenity:
    return await service.get_amenity(db, amenity_id)


@router.patch("/{amenity_id}", response_model=AmenityRead)
async def update_amenity(
    amenity_id: uuid.UUID, payload: AmenityUpdate, db: DbSession, actor_id: ActorId
) -> Amenity:
    return await service.update_amenity(db, amenity_id, payload, actor_id=actor_id)


@router.delete("/{amenity_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_amenity(amenity_id: uuid.UUID, db: DbSession) -> None:
    await service.delete_amenity(db, amenity_id)
