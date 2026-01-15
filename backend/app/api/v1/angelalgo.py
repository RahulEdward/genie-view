"""
AngelAlgo Compatible Endpoints
Endpoints to match OpenAlgo API format for frontend compatibility
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Dict, Any

from app.db.session import get_db
from app.services.auth import AuthService
from app.api.deps import get_api_key
from app.utils.logger import logger

router = APIRouter()


@router.get("/chart")
async def get_chart_preferences_get(
    apikey: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Get user chart preferences (OpenAlgo compatibility) - GET method.
    Accepts apikey from query param.
    """
    if not apikey:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"status": "error", "code": "AUTH_FAILED", "message": "API key required"}
        )
    
    # Validate API key
    auth_service = AuthService(db)
    session = await auth_service.get_session(apikey)
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"status": "error", "code": "AUTH_FAILED", "message": "Invalid API key"}
        )
    
    # Return empty preferences (frontend will use localStorage)
    return {"status": "success", "data": {}}


@router.post("/chart")
async def get_chart_preferences_post(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Save/Get user chart preferences (OpenAlgo compatibility) - POST method.
    Accepts apikey from JSON body.
    """
    # Parse JSON body
    try:
        body = await request.json()
    except Exception:
        body = {}
    
    api_key = body.get("apikey")
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"status": "error", "code": "AUTH_FAILED", "message": "API key required"}
        )
    
    # Validate API key
    auth_service = AuthService(db)
    session = await auth_service.get_session(api_key)
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"status": "error", "code": "AUTH_FAILED", "message": "Invalid API key"}
        )
    
    # Return success (preferences saved - frontend uses localStorage anyway)
    return {"status": "success", "data": {}}


@router.post("/intervals")
async def get_intervals():
    """Get available chart intervals (OpenAlgo compatibility)"""
    return {
        "status": "success",
        "data": [
            "1m", "3m", "5m", "10m", "15m", "30m",
            "1h", "2h", "3h", "4h",
            "D", "W", "M"
        ]
    }


@router.post("/positionbook")
async def get_positions(
    apikey: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Get open positions (OpenAlgo compatibility)"""
    # For now return empty - would need broker integration
    return {"status": "success", "data": []}


@router.post("/orderbook")
async def get_orders(
    apikey: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Get order book (OpenAlgo compatibility)"""
    # For now return empty - would need broker integration
    return {"status": "success", "data": []}


@router.post("/funds")
async def get_funds(
    apikey: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Get account funds (OpenAlgo compatibility)"""
    # For now return empty - would need broker integration
    return {"status": "success", "data": {}}


@router.post("/holdings")
async def get_holdings(
    apikey: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Get holdings (OpenAlgo compatibility)"""
    # For now return empty - would need broker integration
    return {"status": "success", "data": []}


@router.post("/tradebook")
async def get_trades(
    apikey: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Get trade book (OpenAlgo compatibility)"""
    # For now return empty - would need broker integration
    return {"status": "success", "data": []}
