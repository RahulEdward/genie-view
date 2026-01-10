"""
Market Endpoints
Market timings and holidays
"""

from typing import List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.auth import AuthService
from app.services.market_timing import MarketTimingService
from app.models.schemas import (
    MarketTimingsRequest, MarketTimingsResponse, ExchangeTiming,
    MarketHolidaysRequest, MarketHolidaysResponse, HolidayInfo,
    BaseResponse
)
from app.api.deps import default_rate_limiter
from app.utils.logger import logger

router = APIRouter()


class MarketStatusRequest(BaseModel):
    """Market status request"""
    apikey: str
    exchange: str = "NSE"


class MarketStatusData(BaseModel):
    """Market status data"""
    exchange: str
    is_open: bool
    status: str
    message: str
    next_open: str = None
    opens_at: str = None
    closes_at: str = None


class MarketStatusResponse(BaseResponse):
    """Market status response"""
    data: MarketStatusData


@router.post("/timings", response_model=MarketTimingsResponse)
async def get_market_timings(
    request: MarketTimingsRequest,
    db: AsyncSession = Depends(get_db),
    _rate_limit: str = Depends(default_rate_limiter)
):
    """
    Get market timings for exchanges.
    
    - **apikey**: API key from login
    - **date**: Date to get timings for (YYYY-MM-DD)
    
    Returns market open/close times for all exchanges.
    """
    # Validate API key
    auth_service = AuthService(db)
    await auth_service.validate_session(request.apikey)
    
    market_service = MarketTimingService()
    
    try:
        # Get timings for all major exchanges
        exchanges = ["NSE", "BSE", "NFO", "BFO", "MCX", "CDS"]
        timings = []
        
        for exchange in exchanges:
            timing = await market_service.get_timings(exchange)
            
            if "error" not in timing:
                # Convert time strings to epoch milliseconds
                date_str = request.date
                
                open_time = _time_to_epoch(date_str, timing["market_open"])
                close_time = _time_to_epoch(date_str, timing["market_close"])
                
                timings.append(ExchangeTiming(
                    exchange=exchange,
                    start_time=open_time,
                    end_time=close_time
                ))
        
        return MarketTimingsResponse(
            status="success",
            data=timings
        )
        
    except Exception as e:
        logger.error(f"Market timings error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "code": "INTERNAL_ERROR",
                "message": str(e)
            }
        )


@router.post("/holidays", response_model=MarketHolidaysResponse)
async def get_market_holidays(
    request: MarketHolidaysRequest,
    db: AsyncSession = Depends(get_db),
    _rate_limit: str = Depends(default_rate_limiter)
):
    """
    Get market holidays for a year.
    
    - **apikey**: API key from login
    - **year**: Year to get holidays for
    
    Returns list of market holidays.
    """
    # Validate API key
    auth_service = AuthService(db)
    await auth_service.validate_session(request.apikey)
    
    market_service = MarketTimingService()
    
    try:
        holidays = await market_service.get_holidays(request.year)
        
        data = [
            HolidayInfo(
                date=h["date"],
                description=h.get("day", "Holiday"),
                holiday_type="TRADING_HOLIDAY",
                closed_exchanges=["NSE", "BSE", "NFO", "BFO"]
            )
            for h in holidays
        ]
        
        return MarketHolidaysResponse(
            status="success",
            data=data
        )
        
    except Exception as e:
        logger.error(f"Market holidays error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "code": "INTERNAL_ERROR",
                "message": str(e)
            }
        )


@router.post("/status", response_model=MarketStatusResponse)
async def get_market_status(
    request: MarketStatusRequest,
    db: AsyncSession = Depends(get_db),
    _rate_limit: str = Depends(default_rate_limiter)
):
    """
    Get current market status.
    
    - **apikey**: API key from login
    - **exchange**: Exchange code (NSE, BSE, NFO, etc.)
    
    Returns whether market is open/closed and next open time.
    """
    # Validate API key
    auth_service = AuthService(db)
    await auth_service.validate_session(request.apikey)
    
    market_service = MarketTimingService()
    
    try:
        status_info = await market_service.is_market_open(request.exchange)
        
        data = MarketStatusData(
            exchange=status_info["exchange"],
            is_open=status_info["is_open"],
            status=status_info["status"],
            message=status_info["message"],
            next_open=status_info.get("next_open"),
            opens_at=status_info.get("opens_at"),
            closes_at=status_info.get("closes_at")
        )
        
        return MarketStatusResponse(
            status="success",
            data=data
        )
        
    except Exception as e:
        logger.error(f"Market status error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "code": "INTERNAL_ERROR",
                "message": str(e)
            }
        )


def _time_to_epoch(date_str: str, time_str: str) -> int:
    """Convert date and time strings to epoch milliseconds"""
    try:
        dt_str = f"{date_str} {time_str}"
        dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
        return int(dt.timestamp() * 1000)
    except:
        return 0
