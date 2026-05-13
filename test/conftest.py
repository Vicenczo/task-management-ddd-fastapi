"""
Pytest fixtures za test suite - Finalna Windows-Stable verzija.

Strategija:
  - Svaki test kreira sopstveni engine i session (scope="function").
  - Ovo sprečava "RuntimeError: attached to a different loop" na Windowsu.
  - Sadrži dva test korisnika za testiranje dozvola (RBAC).
"""
import os
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.pool import NullPool
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
# Engine Fixture - FUNCTION SCOPE
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture(scope="function")
async def engine():
    """Kreira nov engine za svaki test radi stabilnosti loop-a."""
    test_engine = create_async_engine(
        TEST_DB_URL,
        echo=False,
        poolclass=NullPool,
    )
    yield test_engine
    await test_engine.dispose()

# ---------------------------------------------------------------------------
# Database Setup - Kreira tabele pre svakog testa
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture(scope="function", autouse=True)
async def setup_database(engine):
    """Priprema čistu bazu pre svakog testa."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield

# ---------------------------------------------------------------------------
# DB Session Fixture
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture(scope="function")
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    """Pruža svežu sesiju za trenutni test."""
    TestSessionFactory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )

    async with TestSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

# ---------------------------------------------------------------------------
# Dependency Override
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture(scope="function", autouse=True)
async def override_db(db_session: AsyncSession):
    """Zamenjuje produkcionu sesiju testnom sesijom."""
    async def _get_test_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db_session] = _get_test_session
    yield
    app.dependency_overrides.clear()

# ---------------------------------------------------------------------------
# HTTP Client
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture(scope="function")
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Async klijent za testiranje API-ja."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

# ---------------------------------------------------------------------------
# Test Korisnik 1 (Primarni)
# ---------------------------------------------------------------------------
TEST_USER_1 = {
    "email": "testuser@example.com",
    "username": "testuser",
    "full_name": "Test User",
    "password": "securepassword123",
}

@pytest_asyncio.fixture(scope="function")
async def registered_user(client: AsyncClient) -> dict:
    """Registruje prvog korisnika."""
    response = await client.post("/api/v1/auth/register", json=TEST_USER_1)
    if response.status_code != 201:
         pytest.fail(f"Fixture registered_user failed: {response.text}")
    return response.json()

@pytest_asyncio.fixture(scope="function")
async def auth_token(registered_user: dict) -> str:
    """Vraća token prvog korisnika."""
    return registered_user["token"]["access_token"]

@pytest_asyncio.fixture(scope="function")
def auth_headers(auth_token: str) -> dict:
    """Vraća Authorization header za prvog korisnika."""
    return {"Authorization": f"Bearer {auth_token}"}

# ---------------------------------------------------------------------------
# Test Korisnik 2 (Za testiranje dozvola/RBAC)
# ---------------------------------------------------------------------------
TEST_USER_2 = {
    "email": "seconduser@example.com",
    "username": "seconduser",
    "full_name": "Second User",
    "password": "securepassword456",
}

@pytest_asyncio.fixture(scope="function")
async def registered_user_2(client: AsyncClient) -> dict:
    """Registruje drugog korisnika."""
    response = await client.post("/api/v1/auth/register", json=TEST_USER_2)
    if response.status_code != 201:
        pytest.fail(f"Fixture registered_user_2 failed: {response.text}")
    return response.json()