"""Domain errors for the ``Item`` slice.

These are plain exceptions with no HTTP vocabulary. ``main.py`` maps them onto
status codes, so the service layer can stay framework-free and unit-testable.
"""

from __future__ import annotations

import uuid


class ItemError(Exception):
    """Base class for item domain errors."""


class ItemNotFoundError(ItemError):
    def __init__(self, item_id: uuid.UUID) -> None:
        self.item_id = item_id
        super().__init__(f"Item {item_id} not found")
