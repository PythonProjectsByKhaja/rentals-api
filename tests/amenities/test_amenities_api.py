"""End-to-end tests for the Amenity slice."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration

URL = "/api/v1/amenities"


async def create_amenity(client: AsyncClient, name: str) -> dict[str, object]:
    response = await client.post(URL, json={"name": name})
    assert response.status_code == 201
    body: dict[str, object] = response.json()
    return body


async def test_create_and_read_amenity(client: AsyncClient) -> None:
    creator = uuid.uuid4()
    created = await client.post(URL, json={"name": "Parking"}, headers={"X-User-Id": str(creator)})
    assert created.status_code == 201

    body = created.json()
    assert body["name"] == "Parking"
    assert body["created_by"] == str(creator)

    fetched = await client.get(f"{URL}/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json() == body


async def test_list_amenities_is_sorted_by_name(client: AsyncClient) -> None:
    for name in ("Swimming pool", "Gym", "Power backup"):
        await create_amenity(client, name)

    listed = await client.get(URL)

    assert listed.status_code == 200
    names = [amenity["name"] for amenity in listed.json()]
    assert names == sorted(names)


async def test_duplicate_name_returns_409(client: AsyncClient) -> None:
    await create_amenity(client, "Gym")

    response = await client.post(URL, json={"name": "Gym"})

    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


async def test_rename_amenity(client: AsyncClient) -> None:
    lift = await create_amenity(client, "Lift")
    editor = uuid.uuid4()

    renamed = await client.patch(
        f"{URL}/{lift['id']}", json={"name": "Elevator"}, headers={"X-User-Id": str(editor)}
    )

    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Elevator"
    assert renamed.json()["updated_by"] == str(editor)
    assert (await client.patch(f"{URL}/{lift['id']}", json={"name": None})).status_code == 422


async def test_rename_onto_existing_name_returns_409(client: AsyncClient) -> None:
    await create_amenity(client, "Gym")
    lift = await create_amenity(client, "Lift")

    response = await client.patch(f"{URL}/{lift['id']}", json={"name": "Gym"})

    assert response.status_code == 409
    # The failed update was rolled back.
    assert (await client.get(f"{URL}/{lift['id']}")).json()["name"] == "Lift"


async def test_delete_amenity(client: AsyncClient) -> None:
    amenity = await create_amenity(client, "Club house")

    deleted = await client.delete(f"{URL}/{amenity['id']}")
    assert deleted.status_code == 204

    missing = await client.get(f"{URL}/{amenity['id']}")
    assert missing.status_code == 404


async def test_amenity_in_use_cannot_be_deleted(client: AsyncClient) -> None:
    amenity = await create_amenity(client, "Parking")
    location = await client.post(
        "/api/v1/locations",
        json={"city": "Pune", "locality": "Baner", "state": "Maharashtra"},
    )
    listing = await client.post(
        "/api/v1/properties",
        json={
            "location_id": location.json()["id"],
            "title": "Villa with garden",
            "property_type": "villa",
            "furnishing": "fully_furnished",
            "bedrooms": 4,
            "monthly_rent": 90000,
            "security_deposit": 270000,
            "available_from": "2026-11-01",
            "amenity_ids": [amenity["id"]],
        },
    )
    assert listing.status_code == 201

    response = await client.delete(f"{URL}/{amenity['id']}")

    assert response.status_code == 409
    assert (await client.get(f"{URL}/{amenity['id']}")).status_code == 200
