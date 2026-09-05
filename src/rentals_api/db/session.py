"""Engine, session factory, and the ``get_db`` request dependency."""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from rentals_api.core.config import get_settings

settings = get_settings()

# The engine is created at MODULE scope, not inside the lifespan handler.
#
# httpx's ASGITransport does not run ASGI lifespan events, so a test client
# never triggers startup. An engine built in lifespan would still be None when
# the tests run. Module scope keeps the app importable and testable; lifespan
# only disposes it on shutdown.
engine = create_async_engine(
    settings.sqlalchemy_url,
    pool_pre_ping=True,
    echo=settings.debug,
)

# expire_on_commit=False is not optional here.
#
# After `await session.commit()`, a router returns the ORM object for
# response_model serialization. With expiry on, that attribute access triggers
# lazy IO outside a greenlet context and raises MissingGreenlet.
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncIterator[AsyncSession]:
    """Yield a session for one request.

    The context manager rolls back on exit if nothing was committed.

    Note there is deliberately no ``await session.commit()`` here. Committing in
    the dependency commits even when the handler decided not to, and it fires
    *after* response serialization, which makes error mapping incoherent. The
    service layer owns the transaction boundary.
    """
    async with AsyncSessionLocal() as session:
        yield session
