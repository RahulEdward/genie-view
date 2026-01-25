"""
Historical Data Endpoint
Get OHLC candle data for symbols
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.auth import AuthService
from app.services.market_data import MarketDataService
from app.models.schemas import HistoryRequest, HistoryResponse, OHLCCandle
from app.api.deps import validate_api_key, default_rate_limiter
from app.models.database import UserSession
from app.utils.logger import logger

router = APIRouter()


@router.post("", response_model=HistoryResponse)
async def get_history(
    request: HistoryRequest,
    db: AsyncSession = Depends(get_db),
    _rate_limit: str = Depends(default_rate_limiter)
):
    """
    Get historical OHLC candle data.
    
    - **apikey**: API key from login
    - **symbol**: Trading symbol (e.g., RELIANCE, NIFTY)
    - **exchange**: Exchange code (NSE, BSE, NFO, etc.)
    - **interval**: Candle interval (1m, 5m, 15m, 30m, 1h, 1d, 1w, 1M)
    - **start_date**: Start date (YYYY-MM-DD)
    - **end_date**: End date (YYYY-MM-DD)
    
    Returns list of OHLC candles with IST timestamps.
    """
    # Validate API key
    auth_service = AuthService(db)
    session = await auth_service.validate_session(request.apikey)
    
    # Get broker for session
    broker = await auth_service.get_broker_for_session(session)
    
    # Create market data service
    market_service = MarketDataService(broker, db)
    
    try:
        candles = await market_service.get_history(
            symbol=request.symbol,
            exchange=request.exchange,
            interval=request.interval,
            start_date=request.start_date,
            end_date=request.end_date
        )
        
        # Convert to response format
        data = [
            OHLCCandle(
                timestamp=c["timestamp"],
                open=c["open"],
                high=c["high"],
                low=c["low"],
                close=c["close"],
                volume=c["volume"]
            )
            for c in candles
        ]
        
        logger.info(f"History: {request.symbol} returned {len(data)} candles")
        
        return HistoryResponse(
            status="success",
            data=data
        )
        
    except Exception as e:
        logger.error(f"History error for {request.symbol}: {e}")
        
        # Check for rate limits in error message
        msg = str(e).lower()
        if "rate" in msg and ("limit" in msg or "exceed" in msg) or "429" in msg or "403" in msg:
             raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "status": "error",
                    "code": "RATE_LIMITED",
                    "message": "Broker rate limit exceeded. Please wait."
                }
            )
            
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "code": "BROKER_ERROR",
                "message": str(e)
            }
        )
