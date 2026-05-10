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
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

engine: AsyncEngine = create_async_engine(
    str(settings.DB_URL),
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

AsyncSessionFactory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_db_session() -> AsyncSession:
    """
    Dependency that provides a transactional async database session.
    Rolls back on exception, always closes the session.
    """
    async with AsyncSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


