"""Domain errors for the Location slice.

Plain exceptions with no HTTP vocabulary. ``main.py`` maps them onto status
codes, so the service layer stays framework-free and unit-testable.
"""

from __future__ import annotations

import uuid


class LocationError(Exception):
    """Base class for location domain errors."""


class LocationNotFoundError(LocationError):
    def __init__(self, location_id: uuid.UUID) -> None:
        self.location_id = location_id
        super().__init__(f"Location {location_id} not found")


class LocationInUseError(LocationError):
    def __init__(self, location_id: uuid.UUID) -> None:
        self.location_id = location_id
        super().__init__(
            f"Location {location_id} still has properties; delete or move them first",
        )
