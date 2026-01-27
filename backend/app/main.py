"""
FastAPI Application Entry Point
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.utils.logger import setup_logger, logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Debug mode: {settings.debug}")
    
    # Initialize database connection
    from app.db.session import init_db
    await init_db()
    logger.info("Database initialized")
    
    # Initialize Redis connection
    from app.utils.cache import init_redis
    await init_redis()
    logger.info("Redis cache initialized")
    
    # Initialize instrument master (for option chain functionality)
    try:
        from app.db.session import async_session_maker
        from app.brokers.angelone.adapter import AngelOneAdapter
        from app.services.symbol import SymbolService
        
        logger.info("Initializing instrument master...")
        broker = AngelOneAdapter(api_key="dummy")  # API key not needed for instrument master download
        
        async with async_session_maker() as db:
            symbol_service = SymbolService(broker, db)
            count = await symbol_service.refresh_master(force=False)  # Only refresh if stale
            
            if count > 0:
                logger.info(f"Loaded {count} instruments into master")
            else:
                logger.info("Instrument master already up to date")
                
    except Exception as e:
        logger.warning(f"Instrument master init skipped: {e}")
        # Continue startup - option chain may be limited but app should work
    
    yield
    
    # Shutdown
    logger.info("Shutting down application")
    
    # Close database connection
    from app.db.session import close_db
    await close_db()
    
    # Close Redis connection
    from app.utils.cache import close_redis
    await close_redis()


def create_app() -> FastAPI:
    """Create and configure FastAPI application"""
    
    # Setup logging
    setup_logger(settings.log_level)
    
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Modular Trading Backend with Angel One Integration",
        lifespan=lifespan
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Register exception handlers
    from app.api.exceptions import register_exception_handlers
    register_exception_handlers(app)
    
    # Include API routers
    from app.api.v1.router import api_router
    app.include_router(api_router, prefix="/api/v1")
    
    # Include WebSocket router
    from app.api.websocket import router as ws_router
    app.include_router(ws_router, tags=["WebSocket"])
    
    # Health check endpoint
    @app.get("/health")
    async def health_check():
        return {"status": "healthy", "version": settings.app_version}
    
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )
