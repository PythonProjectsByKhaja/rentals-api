"""Business logic for the Location slice.

Owns the transaction boundary and knows nothing about HTTP.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from rentals_api.locations.exceptions import LocationInUseError, LocationNotFoundError
from rentals_api.locations.models import Location
from rentals_api.locations.schemas import LocationCreate, LocationUpdate

# The foreign key on properties.location_id, named by NAMING_CONVENTION in
# db/base_class.py. It is ON DELETE RESTRICT, so deleting a location that still
# has properties violates it. Matching the constraint by name means this slice
# never has to import the properties slice to check.
PROPERTIES_FK = "fk_properties_location_id_locations"


async def list_locations(
    db: AsyncSession, *, limit: int = 50, offset: int = 0
) -> Sequence[Location]:
    stmt = (
        select(Location)
        .order_by(Location.state, Location.city, Location.locality, Location.id)
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


async def get_location(db: AsyncSession, location_id: uuid.UUID) -> Location:
    location = await db.get(Location, location_id)
    if location is None:
        raise LocationNotFoundError(location_id)
    return location


async def create_location(
    db: AsyncSession, data: LocationCreate, *, actor_id: uuid.UUID | None
) -> Location:
    location = Location(**data.model_dump(), created_by=actor_id, updated_by=actor_id)
    db.add(location)
    await db.commit()
    # refresh() pulls server-generated columns (id, created_at, ...) back from the DB.
    await db.refresh(location)
    return location


async def update_location(
    db: AsyncSession,
    location_id: uuid.UUID,
    data: LocationUpdate,
    *,
    actor_id: uuid.UUID | None,
) -> Location:
    location = await get_location(db, location_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(location, field, value)
    location.updated_by = actor_id
    await db.commit()
    await db.refresh(location)
    return location


async def delete_location(db: AsyncSession, location_id: uuid.UUID) -> None:
    location = await get_location(db, location_id)
    await db.delete(location)
    try:
        await db.commit()
    except IntegrityError as exc:
        # The rollback is mandatory: after an IntegrityError the session refuses
        # every statement until it is cleared. It also expires every loaded
        # object, which is why the error is built from location_id, not from
        # location.id.
        await db.rollback()
        if PROPERTIES_FK in str(exc.orig):
            raise LocationInUseError(location_id) from exc
        raise
