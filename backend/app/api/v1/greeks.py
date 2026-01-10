"""
Greeks Endpoints
Calculate option Greeks (Delta, Gamma, Theta, Vega, IV)
"""

from typing import List, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.auth import AuthService
from app.services.option import OptionService
from app.utils.greeks import calculate_greeks, calculate_greeks_batch
from app.models.schemas import (
    GreeksRequest, GreeksResponse, GreeksData,
    GreeksBatchRequest, BaseResponse
)
from app.api.deps import default_rate_limiter
from app.utils.logger import logger

router = APIRouter()


class GreeksBatchResponse(BaseResponse):
    """Batch Greeks response"""
    data: List[Dict]


@router.post("", response_model=GreeksResponse)
async def get_greeks(
    request: GreeksRequest,
    db: AsyncSession = Depends(get_db),
    _rate_limit: str = Depends(default_rate_limiter)
):
    """
    Calculate Greeks for a single option.
    
    - **apikey**: API key from login
    - **symbol**: Option symbol (e.g., NIFTY30JAN2524000CE)
    - **exchange**: Exchange code (NFO, BFO)
    
    Returns Delta, Gamma, Theta, Vega, and IV.
    """
    # Validate API key
    auth_service = AuthService(db)
    session = await auth_service.validate_session(request.apikey)
    
    # Get broker for session
    broker = await auth_service.get_broker_for_session(session)
    
    try:
        # Get option quote
        quote = await broker.get_quote(request.symbol, request.exchange)
        
        # Parse option details from symbol
        option_info = _parse_option_symbol(request.symbol)
        
        if not option_info:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "code": "INVALID_SYMBOL",
                    "message": "Could not parse option symbol"
                }
            )
        
        # Get underlying LTP
        underlying_quote = await broker.get_quote(
            option_info["underlying"],
            "NSE" if request.exchange == "NFO" else "BSE"
        )
        
        # Calculate Greeks
        greeks = calculate_greeks(
            spot=underlying_quote.ltp,
            strike=option_info["strike"],
            expiry_days=option_info["days_to_expiry"],
            rate=0.07,  # 7% risk-free rate
            option_type=option_info["option_type"],
            option_price=quote.ltp
        )
        
        data = GreeksData(
            delta=greeks.delta,
            gamma=greeks.gamma,
            theta=greeks.theta,
            vega=greeks.vega,
            iv=greeks.iv
        )
        
        logger.debug(f"Greeks: {request.symbol} IV={data.iv}%")
        
        return GreeksResponse(
            status="success",
            data=data
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Greeks error for {request.symbol}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "code": "CALCULATION_ERROR",
                "message": str(e)
            }
        )


@router.post("/batch", response_model=GreeksBatchResponse)
async def get_greeks_batch(
    request: GreeksBatchRequest,
    db: AsyncSession = Depends(get_db),
    _rate_limit: str = Depends(default_rate_limiter)
):
    """
    Calculate Greeks for multiple options.
    
    - **apikey**: API key from login
    - **symbols**: List of {symbol, exchange} dicts
    - **interest_rate**: Optional risk-free rate (default 0.1 = 10%)
    
    Returns list of Greeks for each option.
    """
    # Validate API key
    auth_service = AuthService(db)
    session = await auth_service.validate_session(request.apikey)
    
    # Get broker for session
    broker = await auth_service.get_broker_for_session(session)
    
    try:
        results = []
        
        # Cache underlying prices
        underlying_prices = {}
        
        for sym_info in request.symbols:
            symbol = sym_info.get("symbol", "")
            exchange = sym_info.get("exchange", "NFO")
            
            try:
                # Get option quote
                quote = await broker.get_quote(symbol, exchange)
                
                # Parse option details
                option_info = _parse_option_symbol(symbol)
                
                if not option_info:
                    results.append({
                        "symbol": symbol,
                        "error": "Could not parse option symbol"
                    })
                    continue
                
                # Get underlying price (cached)
                underlying = option_info["underlying"]
                if underlying not in underlying_prices:
                    underlying_exchange = "NSE" if exchange == "NFO" else "BSE"
                    underlying_quote = await broker.get_quote(underlying, underlying_exchange)
                    underlying_prices[underlying] = underlying_quote.ltp
                
                spot = underlying_prices[underlying]
                
                # Calculate Greeks
                greeks = calculate_greeks(
                    spot=spot,
                    strike=option_info["strike"],
                    expiry_days=option_info["days_to_expiry"],
                    rate=request.interest_rate or 0.07,
                    option_type=option_info["option_type"],
                    option_price=quote.ltp
                )
                
                results.append({
                    "symbol": symbol,
                    "exchange": exchange,
                    "delta": greeks.delta,
                    "gamma": greeks.gamma,
                    "theta": greeks.theta,
                    "vega": greeks.vega,
                    "iv": greeks.iv
                })
                
            except Exception as e:
                results.append({
                    "symbol": symbol,
                    "error": str(e)
                })
        
        return GreeksBatchResponse(
            status="success",
            data=results
        )
        
    except Exception as e:
        logger.error(f"Batch Greeks error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "code": "CALCULATION_ERROR",
                "message": str(e)
            }
        )


def _parse_option_symbol(symbol: str) -> Dict:
    """
    Parse option symbol to extract details.
    
    Format: NIFTY30JAN2524000CE
    - Underlying: NIFTY
    - Expiry: 30JAN25
    - Strike: 24000
    - Type: CE/PE
    """
    import re
    from datetime import datetime
    
    # Pattern for Indian option symbols
    pattern = r'^([A-Z]+)(\d{2})([A-Z]{3})(\d{2})(\d+)(CE|PE)$'
    match = re.match(pattern, symbol.upper())
    
    if not match:
        return None
    
    underlying = match.group(1)
    day = match.group(2)
    month = match.group(3)
    year = match.group(4)
    strike = float(match.group(5))
    option_type = match.group(6)
    
    # Calculate days to expiry
    try:
        expiry_str = f"{day}{month}{year}"
        expiry_date = datetime.strptime(expiry_str, "%d%b%y")
        days_to_expiry = max(1, (expiry_date - datetime.now()).days)
    except:
        days_to_expiry = 7  # Default
    
    return {
        "underlying": underlying,
        "expiry": expiry_str,
        "strike": strike,
        "option_type": option_type,
        "days_to_expiry": days_to_expiry
    }
