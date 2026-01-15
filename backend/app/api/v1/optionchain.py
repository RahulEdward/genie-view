"""
Option Chain Endpoint
Get option chain data for underlying symbols
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.auth import AuthService
from app.services.option import OptionService
from app.models.schemas import (
    OptionChainRequest, OptionChainResponse, OptionChainData,
    OptionStrike, OptionLeg
)
from app.api.deps import default_rate_limiter
from app.utils.logger import logger

router = APIRouter()


@router.post("", response_model=OptionChainResponse)
async def get_option_chain(
    request: OptionChainRequest,
    db: AsyncSession = Depends(get_db),
    _rate_limit: str = Depends(default_rate_limiter)
):
    """
    Get option chain for an underlying.
    
    - **apikey**: API key from login
    - **underlying**: Underlying symbol (NIFTY, BANKNIFTY, etc.)
    - **exchange**: Exchange code (NFO, BFO)
    - **expiry**: Optional expiry date (DDMMMYY format, e.g., 30JAN25)
    - **strike_count**: Number of strikes above/below ATM (default 15)
    
    Returns option chain with ATM identification and CE/PE data.
    """
    # Validate API key
    auth_service = AuthService(db)
    session = await auth_service.validate_session(request.apikey)
    
    # Get broker for session
    broker = await auth_service.get_broker_for_session(session)
    
    # Create option service
    option_service = OptionService(broker)
    
    try:
        chain = await option_service.get_option_chain(
            underlying=request.underlying,
            exchange=request.exchange,
            expiry=request.expiry,
            num_strikes=request.strike_count
        )
        
        # Build strike chain
        strikes_map = {}
        
        # Process calls
        for call in chain.get("calls", []):
            strike = call.get("strike", 0)
            if strike not in strikes_map:
                strikes_map[strike] = {"strike": strike, "ce": None, "pe": None}
            
            strikes_map[strike]["ce"] = OptionLeg(
                symbol=call.get("symbol", ""),
                ltp=call.get("ltp", 0),
                prev_close=call.get("prev_close", 0),
                open=call.get("open", 0),
                high=call.get("high", 0),
                low=call.get("low", 0),
                bid=call.get("bid", 0),
                ask=call.get("ask", 0),
                oi=call.get("oi", 0),
                volume=call.get("volume", 0),
                lot_size=call.get("lot_size", 0),
                label=_get_moneyness_label(strike, chain.get("atm_strike", 0), "CE")
            )
        
        # Process puts
        for put in chain.get("puts", []):
            strike = put.get("strike", 0)
            if strike not in strikes_map:
                strikes_map[strike] = {"strike": strike, "ce": None, "pe": None}
            
            strikes_map[strike]["pe"] = OptionLeg(
                symbol=put.get("symbol", ""),
                ltp=put.get("ltp", 0),
                prev_close=put.get("prev_close", 0),
                open=put.get("open", 0),
                high=put.get("high", 0),
                low=put.get("low", 0),
                bid=put.get("bid", 0),
                ask=put.get("ask", 0),
                oi=put.get("oi", 0),
                volume=put.get("volume", 0),
                lot_size=put.get("lot_size", 0),
                label=_get_moneyness_label(strike, chain.get("atm_strike", 0), "PE")
            )
        
        # Sort strikes and build chain
        sorted_strikes = sorted(strikes_map.keys())
        option_chain = [
            OptionStrike(
                strike=s,
                ce=strikes_map[s]["ce"],
                pe=strikes_map[s]["pe"]
            )
            for s in sorted_strikes
        ]
        
        data = OptionChainData(
            underlying=chain.get("underlying", request.underlying),
            underlyingLTP=chain.get("spot_price", 0),
            underlyingPrevClose=0,  # Not always available
            atmStrike=chain.get("atm_strike", 0),
            expiryDate=chain.get("expiry") or request.expiry or "",
            chain=option_chain
        )
        
        logger.debug(f"Option chain: {request.underlying} ATM={data.atmStrike} strikes={len(option_chain)}")
        
        return OptionChainResponse(
            status="success",
            data=data
        )
        
    except Exception as e:
        logger.error(f"Option chain error for {request.underlying}: {e}")
        # Return empty chain instead of 500 error
        empty_data = OptionChainData(
            underlying=request.underlying,
            underlyingLTP=0,
            underlyingPrevClose=0,
            atmStrike=0,
            expiryDate=request.expiry or "",
            chain=[]
        )
        return OptionChainResponse(
            status="success",
            data=empty_data
        )


def _get_moneyness_label(strike: float, atm_strike: float, option_type: str) -> str:
    """Get ITM/ATM/OTM label for an option"""
    if strike == atm_strike:
        return "ATM"
    
    if option_type == "CE":
        return "ITM" if strike < atm_strike else "OTM"
    else:  # PE
        return "ITM" if strike > atm_strike else "OTM"
