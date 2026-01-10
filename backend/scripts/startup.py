#!/usr/bin/env python
"""
Startup Script
Initializes database, runs migrations, and loads instrument master
"""

import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings
from app.db.session import engine, Base
from app.utils.cache import init_redis, close_redis
from app.utils.logger import logger
from app.brokers.factory import get_broker
from app.services.symbol import SymbolService


async def run_migrations():
    """Run Alembic migrations"""
    logger.info("Running database migrations...")
    
    # Use subprocess to run alembic
    import subprocess
    result = subprocess.run(
        ["alembic", "upgrade", "head"],
        capture_output=True,
        text=True,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    
    if result.returncode != 0:
        logger.error(f"Migration failed: {result.stderr}")
        raise RuntimeError("Database migration failed")
    
    logger.info("Migrations completed successfully")


async def create_tables():
    """Create database tables if they don't exist"""
    logger.info("Creating database tables...")
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    logger.info("Database tables created")


async def init_instrument_master():
    """
    Initialize instrument master data.
    Downloads and stores instrument data from broker.
    """
    logger.info("Initializing instrument master...")
    
    try:
        # Get broker adapter
        broker = get_broker()
        
        # Create symbol service
        from app.db.session import async_session
        async with async_session() as db:
            symbol_service = SymbolService(broker, db)
            
            # Refresh instrument master
            count = await symbol_service.refresh_master()
            
            logger.info(f"Loaded {count} instruments into master")
            
    except Exception as e:
        logger.warning(f"Instrument master init failed: {e}")
        logger.info("Instrument master will be loaded on first API call")


async def init_redis_connection():
    """Initialize Redis connection"""
    logger.info("Connecting to Redis...")
    
    try:
        await init_redis()
        logger.info("Redis connected successfully")
    except Exception as e:
        logger.error(f"Redis connection failed: {e}")
        raise


async def startup():
    """Main startup sequence"""
    logger.info("=" * 50)
    logger.info("Trading Backend Startup")
    logger.info("=" * 50)
    
    try:
        # Step 1: Create tables (fallback if migrations fail)
        await create_tables()
        
        # Step 2: Initialize Redis
        await init_redis_connection()
        
        # Step 3: Initialize instrument master (optional, non-blocking)
        try:
            await init_instrument_master()
        except Exception as e:
            logger.warning(f"Instrument master init skipped: {e}")
        
        logger.info("=" * 50)
        logger.info("Startup completed successfully!")
        logger.info("=" * 50)
        
    except Exception as e:
        logger.error(f"Startup failed: {e}")
        raise
    finally:
        await close_redis()


if __name__ == "__main__":
    asyncio.run(startup())
