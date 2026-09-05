"""Smoke tests that need no database.

These always run, even on a fresh clone with nothing started.
"""

from __future__ import annotations

from httpx import AsyncClient


async def test_root_responds(anon_client: AsyncClient) -> None:
    response = await anon_client.get("/")

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "rentals-api"
    assert body["docs"] == "/docs"


async def test_health_is_ok(anon_client: AsyncClient) -> None:
    response = await anon_client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_openapi_schema_is_served(anon_client: AsyncClient) -> None:
    response = await anon_client.get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == "rentals-api"
    # The example slice is mounted under the versioned prefix.
    assert "/api/v1/items" in schema["paths"]
