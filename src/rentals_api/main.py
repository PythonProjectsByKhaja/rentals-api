"""Application entry point."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from rentals_api.amenities.exceptions import (
    AmenityInUseError,
    AmenityNotFoundError,
    DuplicateAmenityNameError,
)
from rentals_api.api.health import router as health_router
from rentals_api.api.router import api_router
from rentals_api.core.config import get_settings
from rentals_api.core.logging import configure_logging
from rentals_api.db.session import engine
from rentals_api.items.exceptions import ItemNotFoundError
from rentals_api.locations.exceptions import LocationInUseError, LocationNotFoundError
from rentals_api.properties.exceptions import (
    PropertyImageNotFoundError,
    PropertyNotFoundError,
    UnknownAmenitiesError,
    UnknownLocationError,
)

settings = get_settings()

# Domain error -> HTTP status code. This table is the ONLY place status codes for
# domain errors are decided, which is what lets services stay framework-free:
# they raise meaning, and main.py maps it. A new domain error needs one line here.
DOMAIN_ERROR_STATUS: dict[type[Exception], int] = {
    ItemNotFoundError: status.HTTP_404_NOT_FOUND,
    LocationNotFoundError: status.HTTP_404_NOT_FOUND,
    AmenityNotFoundError: status.HTTP_404_NOT_FOUND,
    PropertyNotFoundError: status.HTTP_404_NOT_FOUND,
    PropertyImageNotFoundError: status.HTTP_404_NOT_FOUND,
    DuplicateAmenityNameError: status.HTTP_409_CONFLICT,
    LocationInUseError: status.HTTP_409_CONFLICT,
    AmenityInUseError: status.HTTP_409_CONFLICT,
    # The body names a row that does not exist. The request itself is well
    # formed, so this is 422, not 404, which would suggest the URL was wrong.
    UnknownLocationError: status.HTTP_422_UNPROCESSABLE_CONTENT,
    UnknownAmenitiesError: status.HTTP_422_UNPROCESSABLE_CONTENT,
}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup and shutdown.

    The engine is created at import time in ``db.session`` (httpx's
    ASGITransport does not run lifespan events, so tests would otherwise get a
    None engine). All this needs to do is dispose it.

    Disposing explicitly matters on Windows: without it, Proactor event-loop
    transports emit spurious ConnectionResetError from ``__del__`` at
    interpreter shutdown.
    """
    configure_logging(debug=settings.debug)
    yield
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    description="A FastAPI service which lists rentals backed by PostgreSQL.",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    openapi_url="/openapi.json",
)


def _domain_error_handler(
    status_code: int,
) -> Callable[[Request, Exception], Awaitable[JSONResponse]]:
    """Build a handler that renders a domain error as ``{"detail": "<message>"}``."""

    async def handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=status_code, content={"detail": str(exc)})

    return handler


for error_class, error_status in DOMAIN_ERROR_STATUS.items():
    app.add_exception_handler(error_class, _domain_error_handler(error_status))


@app.get("/", tags=["root"])
async def root() -> dict[str, str]:
    """The one endpoint that proves the scaffold is alive."""
    return {
        "name": settings.app_name,
        "environment": settings.environment,
        "docs": "/docs",
    }


app.include_router(health_router)
app.include_router(api_router, prefix=settings.api_v1_prefix)
