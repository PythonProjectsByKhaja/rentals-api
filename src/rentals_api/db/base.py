"""Metadata aggregator -- the single module Alembic imports.

Importing a model module is what registers its table on ``Base.metadata``. If a
model is never imported, ``alembic revision --autogenerate`` cheerfully reports
"no changes detected" and you lose an afternoon to it.

So: **every time you add a model, add a line here.** Automatic discovery via
``pkgutil.walk_packages`` is deliberately avoided -- it silently no-ops when a
package lacks ``__init__.py``, turning a loud failure into a quiet one.

``tests/test_migrations.py`` compares this metadata against the real migrated
schema, so forgetting a line here fails the test suite rather than shipping.
"""

from __future__ import annotations

from rentals_api.amenities.models import Amenity as Amenity
from rentals_api.db.base_class import Base as Base
from rentals_api.items.models import Item as Item
from rentals_api.locations.models import Location as Location
from rentals_api.properties.models import Property as Property
from rentals_api.properties.models import PropertyAmenity as PropertyAmenity
from rentals_api.properties.models import PropertyImage as PropertyImage

__all__ = [
    "Amenity",
    "Base",
    "Item",
    "Location",
    "Property",
    "PropertyAmenity",
    "PropertyImage",
]
