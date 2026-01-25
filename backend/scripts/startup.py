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
    Initialize instrument master data on startup.
    
    Downloads and stores instrument data from broker with retry logic.
    Implements 3 retry attempts with exponential backoff (1s, 2s, 4s).
    Continues startup even if all retries fail.
    """
    logger.info("Initializing instrument master...")
    
    max_retries = 3
    retry_delays = [1, 2, 4]  # Exponential backoff
    
    for attempt in range(max_retries):
        try:
            # Create a dummy broker (not needed for download, but required for SymbolService)
            # The download_instrument_master() method doesn't use the broker
            from app.brokers.angelone.adapter import AngelOneAdapter
            broker = AngelOneAdapter(api_key="dummy")  # API key not needed for instrument master download
            
            # Create symbol service with database session
            from app.db.session import async_session_maker
            async with async_session_maker() as db:
                symbol_service = SymbolService(broker, db)
                
                # Refresh instrument master (force=True to ensure download)
                logger.info(f"Downloading instrument master (attempt {attempt + 1}/{max_retries})...")
                count = await symbol_service.refresh_master(force=True)
                
                if count > 0:
                    logger.info(f"Successfully loaded {count} instruments into master")
                    return  # Success - exit function
                else:
                    logger.warning(f"No instruments loaded on attempt {attempt + 1}")
                    
        except Exception as e:
            logger.error(f"Instrument master init attempt {attempt + 1} failed: {e}")
            
            if attempt < max_retries - 1:
                delay = retry_delays[attempt]
                logger.info(f"Retrying in {delay} seconds...")
                await asyncio.sleep(delay)
            else:
                logger.critical(
                    "Failed to initialize instrument master after all retries. "
                    "Option chain functionality may be limited. "
                    "Continuing startup..."
                )
                return  # Continue startup even after all failures


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
