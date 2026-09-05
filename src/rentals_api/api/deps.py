"""Shared FastAPI dependencies, as reusable ``Annotated`` aliases.

Declaring these once means handlers read as ``db: DbSession`` instead of
repeating ``Depends(get_db)`` everywhere, and there is a single place to change
if the wiring changes.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from rentals_api.core.config import Settings, get_settings
from rentals_api.db.session import get_db

DbSession = Annotated[AsyncSession, Depends(get_db)]

# Depend on this rather than calling get_settings() inline, so tests can
# override it with app.dependency_overrides[get_settings].
SettingsDep = Annotated[Settings, Depends(get_settings)]
