"""
Symbol Search Endpoint
Search for trading symbols
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.auth import AuthService
from app.services.symbol import SymbolService
from app.models.schemas import SearchRequest, SearchResponse, SymbolInfo
from app.api.deps import default_rate_limiter
from app.utils.logger import logger

router = APIRouter()


@router.post("", response_model=SearchResponse)
async def search_symbols(
    request: SearchRequest,
    db: AsyncSession = Depends(get_db),
    _rate_limit: str = Depends(default_rate_limiter)
):
    """
    Search for trading symbols.
    
    - **apikey**: API key from login
    - **query**: Search query (symbol name or trading symbol)
    - **exchange**: Optional exchange filter (NSE, BSE, NFO, etc.)
    
    Returns list of matching symbols with details.
    """
    # Validate API key
    auth_service = AuthService(db)
    session = await auth_service.validate_session(request.apikey)
    
    # Get broker for session
    broker = await auth_service.get_broker_for_session(session)
    
    # Create symbol service
    symbol_service = SymbolService(broker, db)
    
    try:
        results = await symbol_service.search(
            query=request.query,
            exchange=request.exchange,
            limit=20
        )
        
        # Convert to response format
        data = [
            SymbolInfo(
                symbol=r.get("symbol", ""),
                name=r.get("name"),
                exchange=r.get("exchange", ""),
                token=r.get("token", ""),
                instrument_type=r.get("instrument_type"),
                lot_size=r.get("lot_size", 1),
                tick_size=r.get("tick_size", 0.05)
            )
            for r in results
        ]
        
        logger.debug(f"Search: '{request.query}' returned {len(data)} results")
        
        return SearchResponse(
            status="success",
            data=data
        )
        
    except Exception as e:
        logger.error(f"Search error for '{request.query}': {e}")
        # Return empty results instead of 500 error
        return SearchResponse(
            status="success",
            data=[]
        )
