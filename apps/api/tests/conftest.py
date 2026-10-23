import asyncio
import os
import pytest
import pytest_asyncio
from collections.abc import AsyncGenerator
from unittest.mock import patch

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from httpx import AsyncClient, ASGITransport

from app.core.database import Base, get_db
from main import app

# Use in-memory sqlite for fast isolated testing
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestingSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with TestingSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(autouse=True)
def mock_sms_service():
    # Make sure we don't accidentally send real SMS during testing
    with patch("app.services.auth_service.get_sms_service") as mock_sms:
        yield mock_sms

@pytest_asyncio.fixture(autouse=True)
async def db_setup():
    # Create all tables before the test runs
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield
    
    # Drop all tables after the test finishes to ensure isolation
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def session_factory() -> async_sessionmaker[AsyncSession]:
    """The sessions of the test database, for code that opens its own (outside a request)."""
    return TestingSessionLocal
