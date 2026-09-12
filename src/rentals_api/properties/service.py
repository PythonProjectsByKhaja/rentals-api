"""Business logic for the Property slice: properties, their images and amenities.

Owns the transaction boundary and knows nothing about HTTP.

Every read that returns a ``Property`` goes through ``_select_properties()``,
which does two things:

* ``selectinload`` fetches the location, images and amenities in three extra
  queries (not one per property), because the relationships are
  ``lazy="raise"``.
* ``populate_existing`` overwrites an instance the session already holds.
  The relationships are view-only, so writing an image or amenity row does not
  update a collection that was loaded earlier in the same session. Without this
  option the response would show the collection as it was before the write.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable, Sequence

from sqlalchemy import Select, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from rentals_api.amenities.models import Amenity
from rentals_api.locations.models import Location
from rentals_api.properties.exceptions import (
    PropertyImageNotFoundError,
    PropertyNotFoundError,
    UnknownAmenitiesError,
    UnknownLocationError,
)
from rentals_api.properties.models import Property, PropertyAmenity, PropertyImage
from rentals_api.properties.schemas import (
    PropertyCreate,
    PropertyImageCreate,
    PropertyImageUpdate,
    PropertyQuery,
    PropertyUpdate,
)


def _select_properties() -> Select[tuple[Property]]:
    return (
        select(Property)
        .options(
            selectinload(Property.location),
            selectinload(Property.images),
            selectinload(Property.amenities),
        )
        .execution_options(populate_existing=True)
    )


# --- properties --------------------------------------------------------------


async def list_properties(db: AsyncSession, query: PropertyQuery) -> Sequence[Property]:
    stmt = _select_properties()
    if query.city is not None:
        # Case-insensitive exact match. lower() = lower() rather than ILIKE, so a
        # '%' or '_' in the input is not treated as a wildcard.
        stmt = stmt.join(Property.location).where(
            func.lower(Location.city) == func.lower(query.city)
        )
    if query.location_id is not None:
        stmt = stmt.where(Property.location_id == query.location_id)
    if query.property_type is not None:
        stmt = stmt.where(Property.property_type == query.property_type)
    if query.furnishing is not None:
        stmt = stmt.where(Property.furnishing == query.furnishing)
    if query.status is not None:
        stmt = stmt.where(Property.status == query.status)
    if query.min_bedrooms is not None:
        stmt = stmt.where(Property.bedrooms >= query.min_bedrooms)
    if query.min_rent is not None:
        stmt = stmt.where(Property.monthly_rent >= query.min_rent)
    if query.max_rent is not None:
        stmt = stmt.where(Property.monthly_rent <= query.max_rent)

    # id breaks ties, so pages stay stable when created_at values are equal.
    stmt = (
        stmt.order_by(Property.created_at.desc(), Property.id)
        .limit(query.limit)
        .offset(query.offset)
    )
    result = await db.scalars(stmt)
    return result.all()


async def get_property(db: AsyncSession, property_id: uuid.UUID) -> Property:
    """The property with its location, images and amenities loaded."""
    result = await db.scalars(_select_properties().where(Property.id == property_id))
    property_ = result.one_or_none()
    if property_ is None:
        raise PropertyNotFoundError(property_id)
    return property_


async def _get_property_row(db: AsyncSession, property_id: uuid.UUID) -> Property:
    """Just the row, without relationships: enough to change or delete it."""
    property_ = await db.get(Property, property_id)
    if property_ is None:
        raise PropertyNotFoundError(property_id)
    return property_


async def _ensure_location_exists(db: AsyncSession, location_id: uuid.UUID) -> None:
    # Checked up front so the client gets a clear 422 naming the location,
    # rather than a foreign-key violation surfacing as a 500.
    if await db.get(Location, location_id) is None:
        raise UnknownLocationError(location_id)


async def _ensure_amenities_exist(db: AsyncSession, amenity_ids: set[uuid.UUID]) -> None:
    if not amenity_ids:
        return
    found = set(await db.scalars(select(Amenity.id).where(Amenity.id.in_(amenity_ids))))
    missing = amenity_ids - found
    if missing:
        raise UnknownAmenitiesError(missing)


def _amenity_links(
    property_id: uuid.UUID, amenity_ids: Iterable[uuid.UUID], actor_id: uuid.UUID | None
) -> list[PropertyAmenity]:
    return [
        PropertyAmenity(
            property_id=property_id,
            amenity_id=amenity_id,
            created_by=actor_id,
            updated_by=actor_id,
        )
        for amenity_id in amenity_ids
    ]


async def create_property(
    db: AsyncSession, data: PropertyCreate, *, actor_id: uuid.UUID | None
) -> Property:
    await _ensure_location_exists(db, data.location_id)
    await _ensure_amenities_exist(db, data.amenity_ids)

    property_ = Property(
        **data.model_dump(exclude={"amenity_ids"}),
        created_by=actor_id,
        updated_by=actor_id,
    )
    db.add(property_)
    # flush() sends the INSERT now, so the server-generated id is known before
    # the join rows that reference it are added. commit() still decides whether
    # any of it is kept: both inserts land in one transaction.
    await db.flush()
    property_id = property_.id
    db.add_all(_amenity_links(property_id, data.amenity_ids, actor_id))
    await db.commit()
    return await get_property(db, property_id)


async def update_property(
    db: AsyncSession,
    property_id: uuid.UUID,
    data: PropertyUpdate,
    *,
    actor_id: uuid.UUID | None,
) -> Property:
    property_ = await _get_property_row(db, property_id)
    changes = data.model_dump(exclude_unset=True)
    if "location_id" in changes:
        await _ensure_location_exists(db, changes["location_id"])
    for field, value in changes.items():
        setattr(property_, field, value)
    property_.updated_by = actor_id
    await db.commit()
    return await get_property(db, property_id)


async def delete_property(db: AsyncSession, property_id: uuid.UUID) -> None:
    property_ = await _get_property_row(db, property_id)
    # ON DELETE CASCADE removes the property's images and amenity links.
    await db.delete(property_)
    await db.commit()


# --- amenities of a property -------------------------------------------------


async def set_amenities(
    db: AsyncSession,
    property_id: uuid.UUID,
    amenity_ids: set[uuid.UUID],
    *,
    actor_id: uuid.UUID | None,
) -> list[Amenity]:
    """Make the property's amenities exactly ``amenity_ids``.

    Only the difference is written: links being kept are left alone, so they
    keep their original ``created_by`` / ``created_at``.
    """
    await _get_property_row(db, property_id)
    await _ensure_amenities_exist(db, amenity_ids)

    current = set(
        await db.scalars(
            select(PropertyAmenity.amenity_id).where(PropertyAmenity.property_id == property_id)
        )
    )
    removed = current - amenity_ids
    if removed:
        await db.execute(
            delete(PropertyAmenity).where(
                PropertyAmenity.property_id == property_id,
                PropertyAmenity.amenity_id.in_(removed),
            )
        )
    db.add_all(_amenity_links(property_id, amenity_ids - current, actor_id))
    await db.commit()
    return (await get_property(db, property_id)).amenities


# --- images of a property ----------------------------------------------------


async def _get_image(
    db: AsyncSession, property_id: uuid.UUID, image_id: uuid.UUID
) -> PropertyImage:
    # A SELECT filtered on both ids rather than session.get(image_id). It checks
    # that the image belongs to THIS property, and it always asks the database.
    # session.get() can return an image from the identity map even after
    # ON DELETE CASCADE has removed its row.
    stmt = select(PropertyImage).where(
        PropertyImage.id == image_id,
        PropertyImage.property_id == property_id,
    )
    image = (await db.scalars(stmt)).one_or_none()
    if image is None:
        raise PropertyImageNotFoundError(property_id, image_id)
    return image


async def add_image(
    db: AsyncSession,
    property_id: uuid.UUID,
    data: PropertyImageCreate,
    *,
    actor_id: uuid.UUID | None,
) -> PropertyImage:
    await _get_property_row(db, property_id)
    # mode="json" turns the validated HttpUrl object into the plain string the
    # column stores.
    image = PropertyImage(
        **data.model_dump(mode="json"),
        property_id=property_id,
        created_by=actor_id,
        updated_by=actor_id,
    )
    db.add(image)
    await db.commit()
    await db.refresh(image)
    return image


async def update_image(
    db: AsyncSession,
    property_id: uuid.UUID,
    image_id: uuid.UUID,
    data: PropertyImageUpdate,
    *,
    actor_id: uuid.UUID | None,
) -> PropertyImage:
    image = await _get_image(db, property_id, image_id)
    for field, value in data.model_dump(mode="json", exclude_unset=True).items():
        setattr(image, field, value)
    image.updated_by = actor_id
    await db.commit()
    await db.refresh(image)
    return image


async def delete_image(db: AsyncSession, property_id: uuid.UUID, image_id: uuid.UUID) -> None:
    image = await _get_image(db, property_id, image_id)
    await db.delete(image)
    await db.commit()
