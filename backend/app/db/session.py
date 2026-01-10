"""
Database Session Management
Async SQLAlchemy engine and session factory
"""

from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base

from app.config import settings

# Get database URL (uses property that handles empty string)
database_url = settings.db_url

# Create async engine with appropriate settings based on database type
is_sqlite = database_url.startswith("sqlite")

engine_kwargs = {
    "echo": settings.debug,
}

# SQLite doesn't support pool settings
if not is_sqlite:
    engine_kwargs.update({
        "pool_pre_ping": True,
        "pool_size": 10,
        "max_overflow": 20
    })

engine = create_async_engine(database_url, **engine_kwargs)

# Session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

# Base class for models
Base = declarative_base()


async def init_db():
    """Initialize database - create tables"""
    async with engine.begin() as conn:
        # Import models to register them
        from app.models import database  # noqa
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """Close database connection"""
    await engine.dispose()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting database session"""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
