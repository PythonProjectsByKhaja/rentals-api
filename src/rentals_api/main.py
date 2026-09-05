"""Application entry point."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from rentals_api.api.health import router as health_router
from rentals_api.api.router import api_router
from rentals_api.core.config import get_settings
from rentals_api.core.logging import configure_logging
from rentals_api.db.session import engine
from rentals_api.items.exceptions import ItemNotFoundError

settings = get_settings()


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


@app.exception_handler(ItemNotFoundError)
async def item_not_found_handler(request: Request, exc: ItemNotFoundError) -> JSONResponse:
    """Map a domain error to HTTP, so the service layer never imports FastAPI."""
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": str(exc)},
    )


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
