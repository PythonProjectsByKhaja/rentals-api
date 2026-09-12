"""HTTP layer for the Location slice.

Paths, status codes and response models only; logic lives in ``service``.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from fastapi import APIRouter, status

from rentals_api.api.deps import ActorId, DbSession, PageLimit, PageOffset
from rentals_api.locations import service
from rentals_api.locations.models import Location
from rentals_api.locations.schemas import LocationCreate, LocationRead, LocationUpdate

router = APIRouter(prefix="/locations", tags=["locations"])


@router.get("", response_model=list[LocationRead])
async def list_locations(
    db: DbSession, limit: PageLimit = 50, offset: PageOffset = 0
) -> Sequence[Location]:
    return await service.list_locations(db, limit=limit, offset=offset)


@router.post("", response_model=LocationRead, status_code=status.HTTP_201_CREATED)
async def create_location(payload: LocationCreate, db: DbSession, actor_id: ActorId) -> Location:
    return await service.create_location(db, payload, actor_id=actor_id)


@router.get("/{location_id}", response_model=LocationRead)
async def get_location(location_id: uuid.UUID, db: DbSession) -> Location:
    return await service.get_location(db, location_id)


@router.patch("/{location_id}", response_model=LocationRead)
async def update_location(
    location_id: uuid.UUID, payload: LocationUpdate, db: DbSession, actor_id: ActorId
) -> Location:
    return await service.update_location(db, location_id, payload, actor_id=actor_id)


@router.delete("/{location_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_location(location_id: uuid.UUID, db: DbSession) -> None:
    await service.delete_location(db, location_id)
