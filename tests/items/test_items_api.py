"""End-to-end tests for the example slice.

Reference for testing your own features: drive the API through ``client`` and
assert against the same ``session`` the request used.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from rentals_api.items import service
from rentals_api.items.exceptions import ItemNotFoundError
from rentals_api.items.schemas import ItemCreate

pytestmark = pytest.mark.integration


async def test_create_and_read_item(client: AsyncClient) -> None:
    create = await client.post(
        "/api/v1/items",
        json={"name": "widget", "description": "a test widget"},
    )
    assert create.status_code == 201

    created = create.json()
    assert created["name"] == "widget"
    # Server-generated columns come back populated.
    assert created["id"]
    assert created["created_at"]

    fetched = await client.get(f"/api/v1/items/{created['id']}")
    assert fetched.status_code == 200
    assert fetched.json() == created


async def test_list_items(client: AsyncClient) -> None:
    for name in ("alpha", "beta"):
        response = await client.post("/api/v1/items", json={"name": name})
        assert response.status_code == 201

    listed = await client.get("/api/v1/items")
    assert listed.status_code == 200

    names = {item["name"] for item in listed.json()}
    assert {"alpha", "beta"} <= names


async def test_update_item(client: AsyncClient) -> None:
    created = (await client.post("/api/v1/items", json={"name": "before"})).json()

    updated = await client.patch(
        f"/api/v1/items/{created['id']}",
        json={"name": "after"},
    )

    assert updated.status_code == 200
    assert updated.json()["name"] == "after"
    # description was not supplied, so exclude_unset leaves it alone.
    assert updated.json()["description"] == created["description"]


async def test_delete_item(client: AsyncClient) -> None:
    created = (await client.post("/api/v1/items", json={"name": "doomed"})).json()

    deleted = await client.delete(f"/api/v1/items/{created['id']}")
    assert deleted.status_code == 204

    missing = await client.get(f"/api/v1/items/{created['id']}")
    assert missing.status_code == 404


async def test_unknown_item_returns_404(client: AsyncClient) -> None:
    response = await client.get(f"/api/v1/items/{uuid.uuid4()}")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


async def test_validation_rejects_empty_name(client: AsyncClient) -> None:
    response = await client.post("/api/v1/items", json={"name": ""})

    assert response.status_code == 422


async def test_service_raises_domain_error(session: AsyncSession) -> None:
    """The service layer is a plain callable -- no app, no request needed."""
    item = await service.create_item(session, ItemCreate(name="direct"))
    assert item.name == "direct"

    await service.delete_item(session, item.id)

    with pytest.raises(ItemNotFoundError):
        await service.get_item(session, item.id)
