"""
Expiry Dates Endpoint
Get available expiry dates for underlying symbols
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.auth import AuthService
from app.services.option import OptionService
from app.models.schemas import ExpiryRequest, ExpiryResponse
from app.api.deps import default_rate_limiter
from app.utils.logger import logger

router = APIRouter()


@router.post("", response_model=ExpiryResponse)
async def get_expiry_dates(
    request: ExpiryRequest,
    db: AsyncSession = Depends(get_db),
    _rate_limit: str = Depends(default_rate_limiter)
):
    """
    Get available expiry dates for an underlying.
    
    - **apikey**: API key from login
    - **underlying**: Underlying symbol (NIFTY, BANKNIFTY, etc.)
    - **exchange**: Exchange code (NFO, BFO)
    - **instrumenttype**: "options" or "futures"
    
    Returns list of expiry dates in DDMMMYY format, sorted chronologically.
    """
    # Validate API key
    auth_service = AuthService(db)
    session = await auth_service.validate_session(request.apikey)
    
    # Get broker for session
    broker = await auth_service.get_broker_for_session(session)
    
    # Create option service
    option_service = OptionService(broker)
    
    try:
        expiries = await option_service.get_expiry_dates(
            underlying=request.underlying,
            exchange=request.exchange,
            instrument_type=request.instrumenttype
        )
        
        logger.debug(f"Expiry dates: {request.underlying} count={len(expiries)}")
        
        return ExpiryResponse(
            status="success",
            data=expiries
        )
        
    except Exception as e:
        logger.error(f"Expiry error for {request.underlying}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "code": "BROKER_ERROR",
                "message": str(e)
            }
        )
