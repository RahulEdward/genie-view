"""
API v1 Router
Main router that includes all endpoint routers
"""

from fastapi import APIRouter

from app.api.v1 import auth, history, quotes, optionchain, greeks, expiry, search, market, angelalgo

api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(history.router, prefix="/history", tags=["Historical Data"])
api_router.include_router(quotes.router, prefix="/quotes", tags=["Quotes"])
api_router.include_router(optionchain.router, prefix="/optionchain", tags=["Option Chain"])
api_router.include_router(greeks.router, prefix="/greeks", tags=["Greeks"])
api_router.include_router(expiry.router, prefix="/expiry", tags=["Expiry"])
api_router.include_router(search.router, prefix="/search", tags=["Search"])
api_router.include_router(market.router, prefix="/market", tags=["Market"])

# AngelAlgo compatible endpoints (for frontend compatibility)
api_router.include_router(angelalgo.router, tags=["AngelAlgo Compat"])
