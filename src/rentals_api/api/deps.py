"""Shared FastAPI dependencies, as reusable ``Annotated`` aliases.

Declaring these once means handlers read as ``db: DbSession`` instead of
repeating ``Depends(get_db)`` everywhere, and there is a single place to change
if the wiring changes.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, Header, Query
from sqlalchemy.ext.asyncio import AsyncSession

from rentals_api.core.config import Settings, get_settings
from rentals_api.db.session import get_db

DbSession = Annotated[AsyncSession, Depends(get_db)]

# Depend on this rather than calling get_settings() inline, so tests can
# override it with app.dependency_overrides[get_settings].
SettingsDep = Annotated[Settings, Depends(get_settings)]


async def get_actor_id(
    x_user_id: Annotated[uuid.UUID | None, Header()] = None,
) -> uuid.UUID | None:
    """Who is making the request, recorded in the ``created_by``/``updated_by`` columns.

    PLACEHOLDER until the API has authentication. This trusts a client-supplied
    ``X-User-Id`` header, which any caller can forge. When auth arrives, derive
    the id from the verified token here instead. Services take the id as a plain
    argument, so none of them change.
    """
    return x_user_id


ActorId = Annotated[uuid.UUID | None, Depends(get_actor_id)]

# Pagination for list endpoints. The upper bound stops a single request from
# pulling the whole table.
PageLimit = Annotated[int, Query(ge=1, le=100)]
PageOffset = Annotated[int, Query(ge=0)]
