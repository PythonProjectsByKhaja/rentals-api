"""Business logic for the Amenity slice.

Owns the transaction boundary and knows nothing about HTTP.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from rentals_api.amenities.exceptions import (
    AmenityInUseError,
    AmenityNotFoundError,
    DuplicateAmenityNameError,
)
from rentals_api.amenities.models import Amenity
from rentals_api.amenities.schemas import AmenityCreate, AmenityUpdate

# Constraint names come from NAMING_CONVENTION in db/base_class.py. They are what
# let an IntegrityError be turned into the right domain error.
NAME_UNIQUE_CONSTRAINT = "uq_amenities_name"
PROPERTY_LINKS_FK = "fk_property_amenities_amenity_id_amenities"


async def list_amenities(
    db: AsyncSession, *, limit: int = 50, offset: int = 0
) -> Sequence[Amenity]:
    stmt = select(Amenity).order_by(Amenity.name).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return result.scalars().all()


async def get_amenity(db: AsyncSession, amenity_id: uuid.UUID) -> Amenity:
    amenity = await db.get(Amenity, amenity_id)
    if amenity is None:
        raise AmenityNotFoundError(amenity_id)
    return amenity


async def _commit_or_translate(db: AsyncSession, *, name: str) -> None:
    """Commit, turning a duplicate-name violation into a domain error.

    ``name`` is passed in rather than read off the instance afterwards: the
    rollback expires every object in the session, and touching an expired
    attribute here would raise MissingGreenlet.
    """
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        if NAME_UNIQUE_CONSTRAINT in str(exc.orig):
            raise DuplicateAmenityNameError(name) from exc
        raise


async def create_amenity(
    db: AsyncSession, data: AmenityCreate, *, actor_id: uuid.UUID | None
) -> Amenity:
    amenity = Amenity(**data.model_dump(), created_by=actor_id, updated_by=actor_id)
    db.add(amenity)
    await _commit_or_translate(db, name=data.name)
    await db.refresh(amenity)
    return amenity


async def update_amenity(
    db: AsyncSession,
    amenity_id: uuid.UUID,
    data: AmenityUpdate,
    *,
    actor_id: uuid.UUID | None,
) -> Amenity:
    amenity = await get_amenity(db, amenity_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(amenity, field, value)
    amenity.updated_by = actor_id
    await _commit_or_translate(db, name=amenity.name)
    await db.refresh(amenity)
    return amenity


async def delete_amenity(db: AsyncSession, amenity_id: uuid.UUID) -> None:
    amenity = await get_amenity(db, amenity_id)
    await db.delete(amenity)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        if PROPERTY_LINKS_FK in str(exc.orig):
            raise AmenityInUseError(amenity_id) from exc
        raise
