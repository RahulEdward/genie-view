"""
Quotes Endpoint
Get real-time quotes for symbols
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.auth import AuthService
from app.services.market_data import MarketDataService
from app.models.schemas import QuoteRequest, QuoteResponse, QuoteData
from app.api.deps import default_rate_limiter
from app.utils.logger import logger

router = APIRouter()


@router.post("", response_model=QuoteResponse)
async def get_quote(
    request: QuoteRequest,
    db: AsyncSession = Depends(get_db),
    _rate_limit: str = Depends(default_rate_limiter)
):
    """
    Get current quote for a symbol.
    
    - **apikey**: API key from login
    - **symbol**: Trading symbol (e.g., RELIANCE, NIFTY)
    - **exchange**: Exchange code (NSE, BSE, NFO, etc.)
    
    Returns current LTP, OHLC, volume, and change data.
    """
    # Validate API key
    auth_service = AuthService(db)
    session = await auth_service.validate_session(request.apikey)
    
    # Get broker for session
    broker = await auth_service.get_broker_for_session(session)
    
    # Create market data service
    market_service = MarketDataService(broker, db)
    
    try:
        quote = await market_service.get_quote(
            symbol=request.symbol,
            exchange=request.exchange
        )
        
        data = QuoteData(
            ltp=quote["ltp"],
            open=quote["open"],
            high=quote["high"],
            low=quote["low"],
            prev_close=quote["prev_close"],
            volume=quote["volume"],
            change=quote.get("change"),
            change_percent=quote.get("change_percent")
        )
        
        logger.debug(f"Quote: {request.symbol} LTP={data.ltp}")
        
        return QuoteResponse(
            status="success",
            data=data
        )
        
    except Exception as e:
        logger.error(f"Quote error for {request.symbol}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "code": "BROKER_ERROR",
                "message": str(e)
            }
        )
