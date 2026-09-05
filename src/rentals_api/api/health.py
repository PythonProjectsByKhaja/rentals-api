"""Liveness and readiness probes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from sqlalchemy import text

from rentals_api.api.deps import DbSession

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness: the process is up. Deliberately touches nothing external."""
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness(db: DbSession) -> Any:
    """Readiness: dependencies are reachable.

    Returns 503 rather than raising, so an orchestrator sees a clean signal
    instead of a stack trace.
    """
    try:
        await db.execute(text("SELECT 1"))
    # Catching broadly is intentional: the probe must never itself crash.
    except Exception as exc:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unavailable", "detail": str(exc)},
        )
    return {"status": "ready"}
