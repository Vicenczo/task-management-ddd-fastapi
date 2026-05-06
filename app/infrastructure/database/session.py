"""
Async database session management.

Provides:
  - `engine`         — shared async engine (one per process).
  - `AsyncSessionFactory` — callable that produces new sessions.
  - `get_db_session` — FastAPI dependency for request-scoped sessions.

Session lifecycle in a request:
  1. `get_db_session` opens a session.
  2. Route handler (via service/repository) uses it.
  3. On success  -> session.commit() is called.
  4. On any exception -> session.rollback() is called automatically.
  5. Session is always closed in the `finally` block.

This module intentionally has no knowledge of domain entities or ORM models —
it only manages connection state.
"""
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

engine = create_async_engine(
    str(settings.DB_URL),
    # Echo SQL only in DEBUG mode — never in production
    echo=settings.DEBUG,
    # Number of connections kept open in the pool
    pool_size=10,
    max_overflow=20,
    # Seconds to wait for a connection before raising OperationalError
    pool_timeout=30,
    # Recycle connections after 30 minutes to avoid stale connections
    pool_recycle=1800,
    # Verify connection is alive before using it (prevents "SSL connection closed" errors)
    pool_pre_ping=True,
)

# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------

AsyncSessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    # expire_on_commit=False: keep ORM objects usable after commit
    # (important for returning domain entities from service layer)
    expire_on_commit=False,
    autoflush=False,  # We flush manually before queries that need fresh data
    autocommit=False,
)

# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields a request-scoped async DB session.

    Usage in a route:
        async def my_route(session: DbSession) -> ...:
            ...

    The session commits on success and rolls back on any unhandled exception.
    """
    async with AsyncSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# Type alias for cleaner route signatures
DbSession = Annotated[AsyncSession, Depends(get_db_session)]