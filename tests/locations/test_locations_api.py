"""End-to-end tests for the Location slice."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration

URL = "/api/v1/locations"


def payload(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "city": "Hyderabad",
        "locality": "Madhapur",
        "state": "Telangana",
    }
    return base | overrides


def as_user(user_id: uuid.UUID) -> dict[str, str]:
    return {"X-User-Id": str(user_id)}


async def test_create_and_read_location(client: AsyncClient) -> None:
    creator = uuid.uuid4()
    created = await client.post(URL, json=payload(), headers=as_user(creator))
    assert created.status_code == 201

    body = created.json()
    assert body["city"] == "Hyderabad"
    assert body["description"] is None
    # The X-User-Id header fills both audit columns on insert.
    assert body["created_by"] == body["updated_by"] == str(creator)
    assert body["created_at"] and body["updated_at"]

    fetched = await client.get(f"{URL}/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json() == body


async def test_audit_user_is_null_without_header(client: AsyncClient) -> None:
    body = (await client.post(URL, json=payload())).json()

    assert body["created_by"] is None
    assert body["updated_by"] is None


async def test_list_locations(client: AsyncClient) -> None:
    for locality in ("Madhapur", "Gachibowli"):
        assert (await client.post(URL, json=payload(locality=locality))).status_code == 201

    listed = await client.get(URL)

    assert listed.status_code == 200
    assert {"Madhapur", "Gachibowli"} <= {location["locality"] for location in listed.json()}


async def test_update_location_records_the_editor(client: AsyncClient) -> None:
    creator, editor = uuid.uuid4(), uuid.uuid4()
    created = (await client.post(URL, json=payload(), headers=as_user(creator))).json()

    updated = await client.patch(
        f"{URL}/{created['id']}",
        json={"description": "IT corridor"},
        headers=as_user(editor),
    )

    assert updated.status_code == 200
    body = updated.json()
    assert body["description"] == "IT corridor"
    # Fields not sent are untouched, thanks to exclude_unset.
    assert body["city"] == created["city"]
    assert body["created_by"] == str(creator)
    assert body["updated_by"] == str(editor)


async def test_patch_rejects_null_for_required_field(client: AsyncClient) -> None:
    created = (await client.post(URL, json=payload())).json()

    response = await client.patch(f"{URL}/{created['id']}", json={"city": None})

    assert response.status_code == 422


async def test_delete_location(client: AsyncClient) -> None:
    created = (await client.post(URL, json=payload())).json()

    deleted = await client.delete(f"{URL}/{created['id']}")
    assert deleted.status_code == 204

    missing = await client.get(f"{URL}/{created['id']}")
    assert missing.status_code == 404


async def test_location_with_properties_cannot_be_deleted(client: AsyncClient) -> None:
    location = (await client.post(URL, json=payload())).json()
    listing = await client.post(
        "/api/v1/properties",
        json={
            "location_id": location["id"],
            "title": "2BHK near metro",
            "property_type": "apartment",
            "furnishing": "unfurnished",
            "bedrooms": 2,
            "monthly_rent": 20000,
            "security_deposit": 40000,
            "available_from": "2026-10-01",
        },
    )
    assert listing.status_code == 201

    response = await client.delete(f"{URL}/{location['id']}")

    assert response.status_code == 409
    assert "still has properties" in response.json()["detail"]
    # The failed delete was rolled back: the location is still there.
    assert (await client.get(f"{URL}/{location['id']}")).status_code == 200


async def test_unknown_location_returns_404(client: AsyncClient) -> None:
    response = await client.get(f"{URL}/{uuid.uuid4()}")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()
