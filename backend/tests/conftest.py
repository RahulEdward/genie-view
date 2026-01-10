"""
Pytest Configuration and Fixtures
"""

import asyncio
import pytest
from typing import AsyncGenerator
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.main import app
from app.db.session import Base, get_db
from app.config import settings

# Test database URL
TEST_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/trading_test_db"

# Create test engine
test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
test_session_maker = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False
)


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def setup_database():
    """Setup test database"""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db_session(setup_database) -> AsyncGenerator[AsyncSession, None]:
    """Get test database session"""
    async with test_session_maker() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Get test HTTP client"""
    
    async def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
    
    app.dependency_overrides.clear()


@pytest.fixture
def sample_api_key() -> str:
    """Sample API key for testing"""
    return "test_api_key_12345"


@pytest.fixture
def sample_ohlc_data() -> list:
    """Sample OHLC candle data"""
    return [
        {"timestamp": 1704067200, "open": 100.0, "high": 105.0, "low": 99.0, "close": 104.0, "volume": 1000},
        {"timestamp": 1704153600, "open": 104.0, "high": 108.0, "low": 103.0, "close": 107.0, "volume": 1200},
        {"timestamp": 1704240000, "open": 107.0, "high": 110.0, "low": 106.0, "close": 109.0, "volume": 1100},
    ]


@pytest.fixture
def sample_quote_data() -> dict:
    """Sample quote data"""
    return {
        "ltp": 105.50,
        "open": 103.00,
        "high": 107.00,
        "low": 102.50,
        "prev_close": 104.00,
        "volume": 50000
    }
