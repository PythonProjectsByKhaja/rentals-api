"""Domain errors for the Amenity slice.

Plain exceptions with no HTTP vocabulary. ``main.py`` maps them onto status
codes, so the service layer stays framework-free and unit-testable.
"""

from __future__ import annotations

import uuid


class AmenityError(Exception):
    """Base class for amenity domain errors."""


class AmenityNotFoundError(AmenityError):
    def __init__(self, amenity_id: uuid.UUID) -> None:
        self.amenity_id = amenity_id
        super().__init__(f"Amenity {amenity_id} not found")


class DuplicateAmenityNameError(AmenityError):
    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"An amenity named {name!r} already exists")


class AmenityInUseError(AmenityError):
    def __init__(self, amenity_id: uuid.UUID) -> None:
        self.amenity_id = amenity_id
        super().__init__(
            f"Amenity {amenity_id} is assigned to properties; remove it from them first",
        )
