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
    - **underlying** or **symbol**: Underlying symbol (NIFTY, BANKNIFTY, etc.)
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
    
    # Get underlying from either field
    underlying = request.get_underlying
    if not underlying:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "status": "error",
                "code": "VALIDATION_ERROR",
                "message": "Either 'underlying' or 'symbol' is required"
            }
        )
    
    try:
        expiries = await option_service.get_expiry_dates(
            underlying=underlying,
            exchange=request.exchange,
            instrument_type=request.instrumenttype
        )
        
        logger.debug(f"Expiry dates: {underlying} count={len(expiries)}")
        
        return ExpiryResponse(
            status="success",
            data=expiries
        )
        
    except Exception as e:
        logger.error(f"Expiry error for {underlying}: {e}")
        # Return empty list instead of 500 error
        return ExpiryResponse(
            status="success",
            data=[]
        )
