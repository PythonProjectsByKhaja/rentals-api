"""Aggregates every feature router under the versioned API prefix.

Adding a feature slice is one import and one ``include_router`` line here.
"""

from __future__ import annotations

from fastapi import APIRouter

from rentals_api.amenities.router import router as amenities_router
from rentals_api.items.router import router as items_router
from rentals_api.locations.router import router as locations_router
from rentals_api.properties.router import router as properties_router

api_router = APIRouter()
api_router.include_router(items_router)
api_router.include_router(locations_router)
api_router.include_router(amenities_router)
api_router.include_router(properties_router)
