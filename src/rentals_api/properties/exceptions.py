"""Domain errors for the Property slice.

Plain exceptions with no HTTP vocabulary. ``main.py`` maps them onto status
codes, so the service layer stays framework-free and unit-testable.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable


class PropertyError(Exception):
    """Base class for property domain errors."""


class PropertyNotFoundError(PropertyError):
    def __init__(self, property_id: uuid.UUID) -> None:
        self.property_id = property_id
        super().__init__(f"Property {property_id} not found")


class PropertyImageNotFoundError(PropertyError):
    def __init__(self, property_id: uuid.UUID, image_id: uuid.UUID) -> None:
        self.property_id = property_id
        self.image_id = image_id
        super().__init__(f"Image {image_id} not found on property {property_id}")


class UnknownLocationError(PropertyError):
    """The request body names a location that does not exist."""

    def __init__(self, location_id: uuid.UUID) -> None:
        self.location_id = location_id
        super().__init__(f"Location {location_id} does not exist")


class UnknownAmenitiesError(PropertyError):
    """The request body names amenities that do not exist."""

    def __init__(self, amenity_ids: Iterable[uuid.UUID]) -> None:
        self.amenity_ids = sorted(amenity_ids)
        listed = ", ".join(str(amenity_id) for amenity_id in self.amenity_ids)
        super().__init__(f"Amenities do not exist: {listed}")
