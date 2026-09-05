"""Business logic for the ``Item`` slice.

This module owns the transaction boundary and knows nothing about HTTP. It
imports no FastAPI -- and Ruff enforces that (see the ``banned-api`` section in
pyproject.toml), so the rule cannot quietly rot.

The session is passed in explicitly rather than resolved from a dependency,
which keeps these functions ordinary callables you can test with no app and no
request.

Note there is no repository layer. ``AsyncSession`` is already a Unit of Work
plus Data Mapper; a class wrapping ``session.execute(select(Item))`` would add
indirection and buy nothing. Introduce one only when you have a second
persistence backend, or logic complex enough to test with no database at all.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from rentals_api.items.exceptions import ItemNotFoundError
from rentals_api.items.models import Item
from rentals_api.items.schemas import ItemCreate, ItemUpdate


async def list_items(db: AsyncSession, *, limit: int = 50, offset: int = 0) -> Sequence[Item]:
    stmt = select(Item).order_by(Item.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return result.scalars().all()


async def get_item(db: AsyncSession, item_id: uuid.UUID) -> Item:
    item = await db.get(Item, item_id)
    if item is None:
        raise ItemNotFoundError(item_id)
    return item


async def create_item(db: AsyncSession, data: ItemCreate) -> Item:
    item = Item(**data.model_dump())
    db.add(item)
    await db.commit()
    # refresh() pulls server-generated columns (id, created_at) back from the DB.
    await db.refresh(item)
    return item


async def update_item(db: AsyncSession, item_id: uuid.UUID, data: ItemUpdate) -> Item:
    item = await get_item(db, item_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    await db.commit()
    await db.refresh(item)
    return item


async def delete_item(db: AsyncSession, item_id: uuid.UUID) -> None:
    item = await get_item(db, item_id)
    await db.delete(item)
    await db.commit()
