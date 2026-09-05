"""HTTP layer for the ``Item`` slice.

Routers do HTTP and nothing else: paths, status codes, request/response models.
All logic delegates to ``service``. Domain exceptions propagate and are turned
into responses by the handlers registered in ``main.py``.

Handlers are annotated with the ORM type they actually return; ``response_model``
is what converts that to the wire format, so the annotation stays honest and
mypy can check it.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from fastapi import APIRouter, status

from rentals_api.api.deps import DbSession
from rentals_api.items import service
from rentals_api.items.models import Item
from rentals_api.items.schemas import ItemCreate, ItemRead, ItemUpdate

router = APIRouter(prefix="/items", tags=["items"])


@router.get("", response_model=list[ItemRead])
async def list_items(db: DbSession, limit: int = 50, offset: int = 0) -> Sequence[Item]:
    return await service.list_items(db, limit=limit, offset=offset)


@router.post("", response_model=ItemRead, status_code=status.HTTP_201_CREATED)
async def create_item(payload: ItemCreate, db: DbSession) -> Item:
    return await service.create_item(db, payload)


@router.get("/{item_id}", response_model=ItemRead)
async def get_item(item_id: uuid.UUID, db: DbSession) -> Item:
    return await service.get_item(db, item_id)


@router.patch("/{item_id}", response_model=ItemRead)
async def update_item(item_id: uuid.UUID, payload: ItemUpdate, db: DbSession) -> Item:
    return await service.update_item(db, item_id, payload)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(item_id: uuid.UUID, db: DbSession) -> None:
    await service.delete_item(db, item_id)
