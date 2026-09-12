"""End-to-end tests for the Property slice: properties, their images and amenities."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from rentals_api.locations.models import Location
from rentals_api.properties import service
from rentals_api.properties.exceptions import UnknownAmenitiesError
from rentals_api.properties.models import Furnishing, PropertyAmenity, PropertyImage, PropertyType
from rentals_api.properties.schemas import PropertyCreate

pytestmark = pytest.mark.integration

URL = "/api/v1/properties"


async def create_location(
    client: AsyncClient, city: str = "Hyderabad", locality: str = "Madhapur"
) -> str:
    response = await client.post(
        "/api/v1/locations",
        json={"city": city, "locality": locality, "state": "Telangana"},
    )
    assert response.status_code == 201
    return str(response.json()["id"])


async def create_amenity(client: AsyncClient, name: str) -> str:
    response = await client.post("/api/v1/amenities", json={"name": name})
    assert response.status_code == 201
    return str(response.json()["id"])


def payload(location_id: str, **overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "location_id": location_id,
        "title": "2BHK near metro",
        "property_type": "apartment",
        "furnishing": "semi_furnished",
        "bedrooms": 2,
        "monthly_rent": "25000",
        "security_deposit": "50000",
        "carpet_area_sqft": 1100,
        "available_from": "2026-10-01",
    }
    return base | overrides


def as_user(user_id: uuid.UUID) -> dict[str, str]:
    return {"X-User-Id": str(user_id)}


# --- properties --------------------------------------------------------------


async def test_create_property_embeds_location_and_amenities(client: AsyncClient) -> None:
    location_id = await create_location(client)
    parking = await create_amenity(client, "Parking")
    gym = await create_amenity(client, "Gym")
    creator = uuid.uuid4()

    created = await client.post(
        URL,
        json=payload(location_id, amenity_ids=[parking, gym]),
        headers=as_user(creator),
    )
    assert created.status_code == 201

    body = created.json()
    assert body["status"] == "available"  # the default
    # Decimal is serialized as a string, so no float rounding creeps in.
    assert body["monthly_rent"] == "25000.00"
    assert body["location"] == {
        "id": location_id,
        "city": "Hyderabad",
        "locality": "Madhapur",
        "state": "Telangana",
    }
    assert [amenity["name"] for amenity in body["amenities"]] == ["Gym", "Parking"]
    assert body["images"] == []
    assert body["created_by"] == body["updated_by"] == str(creator)

    fetched = await client.get(f"{URL}/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json() == body


async def test_unknown_location_or_amenity_returns_422(client: AsyncClient) -> None:
    location_id = await create_location(client)
    missing = str(uuid.uuid4())

    no_location = await client.post(URL, json=payload(missing))
    assert no_location.status_code == 422
    assert missing in no_location.json()["detail"]

    no_amenity = await client.post(URL, json=payload(location_id, amenity_ids=[missing]))
    assert no_amenity.status_code == 422
    assert missing in no_amenity.json()["detail"]


@pytest.mark.parametrize(
    "override",
    [
        {"property_type": "castle"},
        {"furnishing": "half"},
        {"bedrooms": -1},
        {"monthly_rent": "-1"},
        {"monthly_rent": "100.555"},  # more than two decimal places
        {"carpet_area_sqft": 0},
    ],
)
async def test_invalid_property_is_rejected(
    client: AsyncClient, override: dict[str, object]
) -> None:
    location_id = await create_location(client)

    response = await client.post(URL, json=payload(location_id, **override))

    assert response.status_code == 422


async def test_list_filters(client: AsyncClient) -> None:
    hyderabad = await create_location(client, city="Hyderabad", locality="Kondapur")
    pune = await create_location(client, city="Pune", locality="Baner")
    listings = [
        ("hyd-cheap", hyderabad, 15000, 1, "available"),
        ("hyd-big", hyderabad, 45000, 3, "available"),
        ("hyd-rented", hyderabad, 30000, 2, "rented"),
        ("pune-mid", pune, 25000, 2, "available"),
    ]
    for title, location_id, rent, bedrooms, status in listings:
        response = await client.post(
            URL,
            json=payload(
                location_id, title=title, monthly_rent=rent, bedrooms=bedrooms, status=status
            ),
        )
        assert response.status_code == 201

    async def titles(**params: str | int) -> set[str]:
        response = await client.get(URL, params=params)
        assert response.status_code == 200
        return {listing["title"] for listing in response.json()}

    # city matching is case-insensitive
    assert await titles(city="hyderabad") == {"hyd-cheap", "hyd-big", "hyd-rented"}
    assert await titles(city="hyderabad", status="available") == {"hyd-cheap", "hyd-big"}
    assert await titles(max_rent=25000) == {"hyd-cheap", "pune-mid"}
    assert await titles(min_rent=25000, max_rent=40000) == {"hyd-rented", "pune-mid"}
    assert await titles(min_bedrooms=3) == {"hyd-big"}
    assert await titles(location_id=pune) == {"pune-mid"}
    assert await titles(property_type="apartment", furnishing="semi_furnished") == {
        "hyd-cheap",
        "hyd-big",
        "hyd-rented",
        "pune-mid",
    }
    assert await titles(property_type="villa") == set()
    assert await titles(furnishing="fully_furnished") == set()
    assert len(await titles(limit=2)) == 2


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 101}, {"status": "sold"}])
async def test_list_rejects_bad_query(client: AsyncClient, params: dict[str, object]) -> None:
    response = await client.get(URL, params=params)

    assert response.status_code == 422


async def test_update_property(client: AsyncClient) -> None:
    location_id = await create_location(client)
    creator, editor = uuid.uuid4(), uuid.uuid4()
    created = (await client.post(URL, json=payload(location_id), headers=as_user(creator))).json()

    response = await client.patch(
        f"{URL}/{created['id']}",
        json={"monthly_rent": "27000", "status": "rented", "carpet_area_sqft": None},
        headers=as_user(editor),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["monthly_rent"] == "27000.00"
    assert body["status"] == "rented"
    # carpet_area_sqft is nullable, so an explicit null clears it.
    assert body["carpet_area_sqft"] is None
    # Fields not sent are untouched.
    assert body["title"] == created["title"]
    assert body["created_by"] == str(creator)
    assert body["updated_by"] == str(editor)


async def test_update_moves_property_to_another_location(client: AsyncClient) -> None:
    madhapur = await create_location(client, locality="Madhapur")
    gachibowli = await create_location(client, locality="Gachibowli")
    created = (await client.post(URL, json=payload(madhapur))).json()

    moved = await client.patch(f"{URL}/{created['id']}", json={"location_id": gachibowli})
    assert moved.status_code == 200
    # The embedded location reflects the move, not the location loaded earlier.
    assert moved.json()["location"]["locality"] == "Gachibowli"

    nowhere = await client.patch(f"{URL}/{created['id']}", json={"location_id": str(uuid.uuid4())})
    assert nowhere.status_code == 422


@pytest.mark.parametrize("field", ["title", "monthly_rent", "status", "location_id"])
async def test_patch_rejects_null_for_required_field(client: AsyncClient, field: str) -> None:
    location_id = await create_location(client)
    created = (await client.post(URL, json=payload(location_id))).json()

    response = await client.patch(f"{URL}/{created['id']}", json={field: None})

    assert response.status_code == 422


async def test_delete_property_removes_its_images_and_amenity_links(
    client: AsyncClient, session: AsyncSession
) -> None:
    location_id = await create_location(client)
    parking = await create_amenity(client, "Parking")
    created = (await client.post(URL, json=payload(location_id, amenity_ids=[parking]))).json()
    image = await client.post(
        f"{URL}/{created['id']}/images",
        json={"url": "https://img.example.com/p/1.jpg"},
    )
    assert image.status_code == 201

    assert (await client.delete(f"{URL}/{created['id']}")).status_code == 204
    assert (await client.get(f"{URL}/{created['id']}")).status_code == 404

    # ON DELETE CASCADE removed the child rows in the database...
    property_id = uuid.UUID(created["id"])
    for model in (PropertyImage, PropertyAmenity):
        remaining = await session.scalar(
            select(func.count()).select_from(model).where(model.property_id == property_id)
        )
        assert remaining == 0
    # ...so the amenity is no longer in use and can be deleted.
    assert (await client.delete(f"/api/v1/amenities/{parking}")).status_code == 204


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("GET", "", None),
        ("PATCH", "", {"title": "x"}),
        ("DELETE", "", None),
        ("PUT", "/amenities", {"amenity_ids": []}),
        ("POST", "/images", {"url": "https://img.example.com/p/1.jpg"}),
    ],
)
async def test_unknown_property_returns_404(
    client: AsyncClient, method: str, path: str, body: dict[str, object] | None
) -> None:
    response = await client.request(method, f"{URL}/{uuid.uuid4()}{path}", json=body)

    assert response.status_code == 404


# --- amenities of a property -------------------------------------------------


async def test_set_amenities_replaces_the_set(client: AsyncClient, session: AsyncSession) -> None:
    location_id = await create_location(client)
    wifi, parking, gym = [await create_amenity(client, name) for name in ("WiFi", "Parking", "Gym")]
    first_user, second_user = uuid.uuid4(), uuid.uuid4()
    created = (
        await client.post(
            URL,
            json=payload(location_id, amenity_ids=[wifi, parking]),
            headers=as_user(first_user),
        )
    ).json()

    response = await client.put(
        f"{URL}/{created['id']}/amenities",
        json={"amenity_ids": [parking, gym]},
        headers=as_user(second_user),
    )

    assert response.status_code == 200
    assert [amenity["name"] for amenity in response.json()] == ["Gym", "Parking"]
    fetched = (await client.get(f"{URL}/{created['id']}")).json()
    assert [amenity["name"] for amenity in fetched["amenities"]] == ["Gym", "Parking"]

    # Only the difference was written: the kept link still records who first
    # attached it, and the new link records the second user.
    rows = await session.execute(
        select(PropertyAmenity.amenity_id, PropertyAmenity.created_by).where(
            PropertyAmenity.property_id == uuid.UUID(created["id"])
        )
    )
    # .all() matters: a Result has a keys() method, so dict(result) would try to
    # treat it as a mapping instead of iterating its rows.
    links = dict(rows.tuples().all())
    assert links == {uuid.UUID(parking): first_user, uuid.UUID(gym): second_user}

    cleared = await client.put(f"{URL}/{created['id']}/amenities", json={"amenity_ids": []})
    assert cleared.status_code == 200
    assert cleared.json() == []


# --- images of a property ----------------------------------------------------


async def test_image_lifecycle(client: AsyncClient) -> None:
    location_id = await create_location(client)
    property_id = (await client.post(URL, json=payload(location_id))).json()["id"]
    images_url = f"{URL}/{property_id}/images"

    second = await client.post(
        images_url, json={"url": "https://img.example.com/p/2.jpg", "position": 1}
    )
    first = await client.post(images_url, json={"url": "https://img.example.com/p/1.jpg"})
    assert second.status_code == first.status_code == 201
    assert first.json()["position"] == 0  # the default

    def urls(listing: dict[str, list[dict[str, object]]]) -> list[object]:
        return [image["url"] for image in listing["images"]]

    # Images come back ordered by position, not by insertion order.
    listing = (await client.get(f"{URL}/{property_id}")).json()
    assert urls(listing) == ["https://img.example.com/p/1.jpg", "https://img.example.com/p/2.jpg"]

    moved = await client.patch(f"{images_url}/{first.json()['id']}", json={"position": 5})
    assert moved.status_code == 200
    listing = (await client.get(f"{URL}/{property_id}")).json()
    assert urls(listing) == ["https://img.example.com/p/2.jpg", "https://img.example.com/p/1.jpg"]

    deleted = await client.delete(f"{images_url}/{second.json()['id']}")
    assert deleted.status_code == 204
    assert (await client.delete(f"{images_url}/{second.json()['id']}")).status_code == 404


async def test_image_is_scoped_to_its_property(client: AsyncClient) -> None:
    location_id = await create_location(client)
    owner = (await client.post(URL, json=payload(location_id))).json()["id"]
    other = (await client.post(URL, json=payload(location_id))).json()["id"]
    image = (
        await client.post(f"{URL}/{owner}/images", json={"url": "https://img.example.com/a.jpg"})
    ).json()

    response = await client.patch(f"{URL}/{other}/images/{image['id']}", json={"position": 1})

    assert response.status_code == 404


@pytest.mark.parametrize(
    "body",
    [
        {"url": "not a url"},
        {"url": "ftp://img.example.com/a.jpg"},
        {"url": "https://x.io/a.jpg", "position": -1},
    ],
)
async def test_invalid_image_is_rejected(client: AsyncClient, body: dict[str, object]) -> None:
    location_id = await create_location(client)
    property_id = (await client.post(URL, json=payload(location_id))).json()["id"]

    response = await client.post(f"{URL}/{property_id}/images", json=body)

    assert response.status_code == 422


# --- the service layer on its own --------------------------------------------


async def test_service_reports_every_missing_amenity(session: AsyncSession) -> None:
    """The service layer is a plain callable -- no app, no request needed."""
    location = Location(city="Chennai", locality="Adyar", state="Tamil Nadu")
    session.add(location)
    await session.flush()
    missing = {uuid.uuid4(), uuid.uuid4()}

    with pytest.raises(UnknownAmenitiesError) as excinfo:
        await service.create_property(
            session,
            PropertyCreate(
                location_id=location.id,
                title="Sea-facing flat",
                property_type=PropertyType.APARTMENT,
                furnishing=Furnishing.FULLY_FURNISHED,
                bedrooms=3,
                monthly_rent=Decimal("60000"),
                security_deposit=Decimal("180000"),
                available_from=date(2026, 12, 1),
                amenity_ids=missing,
            ),
            actor_id=None,
        )

    assert set(excinfo.value.amenity_ids) == missing
