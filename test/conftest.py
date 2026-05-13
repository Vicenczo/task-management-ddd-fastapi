"""
Pytest fixtures for the test suite.

Test database strategy:
  - Uses a SEPARATE PostgreSQL database (taskapi_test_db) — NOT SQLite.
  - Razlog: koristimo PostgreSQL-specifičan ARRAY tip za tags u TaskModel.
    SQLite ne podržava ARRAY — testovi bi pali na schema kreaciji.
  - Svaki test modul dobija čistu bazu (truncate između testova, ne drop/create).
  - Tabele se kreiraju jednom po test sesiji via Alembic `upgrade head`.

Env varijable za test bazu:
  TEST_DB_URL=postgresql+asyncpg://taskapi:taskapi_secret@localhost:5432/taskapi_test_db

  Ako TEST_DB_URL nije setovan, koristi se default (lokalni Docker).
"""
import asyncio
import os
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.infrastructure.database.models import Base
from app.infrastructure.database.session import get_db_session
from app.main import app

# ---------------------------------------------------------------------------
# Test database URL
# ---------------------------------------------------------------------------

TEST_DB_URL: str = os.getenv(
    "TEST_DB_URL",
    "postgresql+asyncpg://taskapi:taskapi_secret@localhost:5432/taskapi_test_db",
)

# ---------------------------------------------------------------------------
# Engine and session factory for test DB
# ---------------------------------------------------------------------------

test_engine = create_async_engine(
    TEST_DB_URL,
    echo=False,
    pool_pre_ping=True,
)

TestSessionFactory = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


# ---------------------------------------------------------------------------
# Session-scoped: create tables once per pytest run
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(scope="session", autouse=True)
async def create_test_tables():
    """
    Create all tables at the start of the test session.
    Drop them after all tests complete.
    Runs once per pytest invocation — not per test.
    """
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


# ---------------------------------------------------------------------------
# Function-scoped: clean data between tests
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(autouse=True)
async def clean_tables():
    """
    Truncate all tables between tests so each test starts with a clean state.
    ORDER matters — FK constraints: tasks → project_members → projects → users.
    """
    yield
    async with test_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())


# ---------------------------------------------------------------------------
# Override FastAPI's get_db_session with test session
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a test-scoped async session connected to the test database."""
    async with TestSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@pytest_asyncio.fixture(autouse=True)
async def override_db(db_session: AsyncSession):
    """
    Override the get_db_session dependency for every test.
    FastAPI will inject the test session instead of the production session.
    """
    async def _get_test_session():
        yield db_session

    app.dependency_overrides[get_db_session] = _get_test_session
    yield
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# HTTP client
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """
    Async HTTP client connected to the test application.
    Uses ASGI transport — no real network calls.
    """
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


# ---------------------------------------------------------------------------
# Convenience fixtures: pre-registered user + auth token
# ---------------------------------------------------------------------------

TEST_USER = {
    "email": "testuser@example.com",
    "username": "testuser",
    "full_name": "Test User",
    "password": "securepassword123",
}

TEST_USER_2 = {
    "email": "seconduser@example.com",
    "username": "seconduser",
    "full_name": "Second User",
    "password": "securepassword456",
}


@pytest_asyncio.fixture
async def registered_user(client: AsyncClient) -> dict:
    """Register TEST_USER and return the response body."""
    response = await client.post("/api/v1/auth/register", json=TEST_USER)
    assert response.status_code == 201, response.text
    return response.json()


@pytest_asyncio.fixture
async def auth_token(registered_user: dict) -> str:
    """Return the JWT access token for TEST_USER."""
    return registered_user["token"]["access_token"]


@pytest_asyncio.fixture
def auth_headers(auth_token: str) -> dict:
    """Return Authorization headers for TEST_USER."""
    return {"Authorization": f"Bearer {auth_token}"}


@pytest_asyncio.fixture
async def registered_user_2(client: AsyncClient) -> dict:
    """Register TEST_USER_2 and return the response body."""
    response = await client.post("/api/v1/auth/register", json=TEST_USER_2)
    assert response.status_code == 201, response.text
    return response.json()