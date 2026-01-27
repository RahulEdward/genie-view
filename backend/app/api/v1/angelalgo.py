"""
AngelAlgo Compatible Endpoints
Endpoints to match OpenAlgo API format for frontend compatibility
"""

import asyncio
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Dict, Any

from app.db.session import get_db
from app.services.auth import AuthService
from app.api.deps import get_api_key
from app.utils.logger import logger

router = APIRouter()

# In-memory cache for account data (short TTL to reduce API calls)
_account_cache: Dict[str, Dict[str, Any]] = {}
_cache_ttl = 30  # 30 seconds cache for account data


def _get_cached(client_id: str, key: str) -> Optional[Any]:
    """Get cached data if not expired"""
    cache_key = f"{client_id}:{key}"
    if cache_key in _account_cache:
        entry = _account_cache[cache_key]
        if datetime.now() < entry["expires"]:
            logger.debug(f"Cache hit for {cache_key}")
            return entry["data"]
        else:
            del _account_cache[cache_key]
    return None


def _set_cached(client_id: str, key: str, data: Any, ttl: int = None):
    """Set cached data with TTL"""
    cache_key = f"{client_id}:{key}"
    _account_cache[cache_key] = {
        "data": data,
        "expires": datetime.now() + timedelta(seconds=ttl or _cache_ttl)
    }


# Rate limiter for broker API calls
_last_api_call: Dict[str, datetime] = {}
_min_interval = 1.0  # Minimum 1 second between API calls per client


async def _rate_limit(client_id: str):
    """Simple rate limiter to prevent too many API calls"""
    now = datetime.now()
    if client_id in _last_api_call:
        elapsed = (now - _last_api_call[client_id]).total_seconds()
        if elapsed < _min_interval:
            await asyncio.sleep(_min_interval - elapsed)
    _last_api_call[client_id] = datetime.now()



@router.post("/ping")
async def ping():
    return {"status": "success", "message": "Pong"}


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
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Get open positions (OpenAlgo compatibility) - with caching"""
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
    
    # Validate API key and get broker adapter
    auth_service = AuthService(db)
    session = await auth_service.get_session(api_key)
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"status": "error", "code": "AUTH_FAILED", "message": "Invalid API key"}
        )
    
    # Check cache first
    cached = _get_cached(session.client_id, "positions")
    if cached is not None:
        return {"status": "success", "data": cached}
    
    try:
        # Rate limit API calls
        await _rate_limit(session.client_id)
        
        broker = await auth_service.get_broker_for_session(session)
        positions = await broker.get_positions()
        
        # Cache the result
        _set_cached(session.client_id, "positions", positions, ttl=30)
        
        return {"status": "success", "data": positions}
    except Exception as e:
        logger.error(f"Error fetching positions: {e}")
        return {"status": "success", "data": []}


@router.post("/orderbook")
async def get_orders(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Get order book (OpenAlgo compatibility) - with caching"""
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
    
    # Validate API key and get broker adapter
    auth_service = AuthService(db)
    session = await auth_service.get_session(api_key)
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"status": "error", "code": "AUTH_FAILED", "message": "Invalid API key"}
        )
    
    # Check cache first
    cached = _get_cached(session.client_id, "orders")
    if cached is not None:
        return {"status": "success", "data": {"orders": cached, "statistics": {}}}
    
    try:
        # Rate limit API calls
        await _rate_limit(session.client_id)
        
        broker = await auth_service.get_broker_for_session(session)
        orders = await broker.get_orders()
        
        # Cache the result
        _set_cached(session.client_id, "orders", orders, ttl=15)  # Shorter TTL for orders
        
        return {"status": "success", "data": {"orders": orders, "statistics": {}}}
    except Exception as e:
        logger.error(f"Error fetching orders: {e}")
        return {"status": "success", "data": {"orders": [], "statistics": {}}}


@router.post("/funds")
async def get_funds(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Get account funds (OpenAlgo compatibility) - with caching"""
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
    
    # Validate API key and get broker adapter
    auth_service = AuthService(db)
    session = await auth_service.get_session(api_key)
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"status": "error", "code": "AUTH_FAILED", "message": "Invalid API key"}
        )
    
    # Check cache first
    cached = _get_cached(session.client_id, "funds")
    if cached is not None:
        return {"status": "success", "data": cached}
    
    try:
        # Rate limit API calls
        await _rate_limit(session.client_id)
        
        broker = await auth_service.get_broker_for_session(session)
        funds = await broker.get_funds()
        
        # Cache the result
        _set_cached(session.client_id, "funds", funds, ttl=60)  # Longer TTL for funds
        
        return {"status": "success", "data": funds}
    except Exception as e:
        logger.error(f"Error fetching funds: {e}")
        return {"status": "success", "data": {}}


@router.post("/holdings")
async def get_holdings(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Get holdings (OpenAlgo compatibility) - with caching"""
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
    
    # Validate API key and get broker adapter
    auth_service = AuthService(db)
    session = await auth_service.get_session(api_key)
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"status": "error", "code": "AUTH_FAILED", "message": "Invalid API key"}
        )
    
    # Check cache first
    cached = _get_cached(session.client_id, "holdings")
    if cached is not None:
        return {"status": "success", "data": {"holdings": cached, "statistics": {}}}
    
    try:
        # Rate limit API calls
        await _rate_limit(session.client_id)
        
        broker = await auth_service.get_broker_for_session(session)
        holdings = await broker.get_holdings()
        
        # Cache the result
        _set_cached(session.client_id, "holdings", holdings, ttl=120)  # Longer TTL for holdings
        
        return {"status": "success", "data": {"holdings": holdings, "statistics": {}}}
    except Exception as e:
        logger.error(f"Error fetching holdings: {e}")
        return {"status": "success", "data": {"holdings": [], "statistics": {}}}


@router.post("/tradebook")
async def get_trades(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Get trade book (OpenAlgo compatibility) - with caching"""
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
    
    # Validate API key and get broker adapter
    auth_service = AuthService(db)
    session = await auth_service.get_session(api_key)
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"status": "error", "code": "AUTH_FAILED", "message": "Invalid API key"}
        )
    
    # Check cache first
    cached = _get_cached(session.client_id, "trades")
    if cached is not None:
        return {"status": "success", "data": cached}
    
    try:
        # Rate limit API calls
        await _rate_limit(session.client_id)
        
        broker = await auth_service.get_broker_for_session(session)
        trades = await broker.get_trades()
        
        # Cache the result
        _set_cached(session.client_id, "trades", trades, ttl=30)
        
        return {"status": "success", "data": trades}
    except Exception as e:
        logger.error(f"Error fetching trades: {e}")
        return {"status": "success", "data": []}


@router.post("/placeorder")
async def place_order(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Place order (OpenAlgo compatibility)"""
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
    
    try:
        broker = await auth_service.get_broker_for_session(session)
        # Pass the entire body as params (contains symbol, action, etc.)
        response = await broker.place_order(body)
        
        # Format response for frontend
        if response.get("status"):
            return {
                "status": "success",
                "message": "Order placed successfully",
                "orderid": response.get("data", {}).get("orderid"),
                "script": body.get("symbol") # Optional
            }
        else:
            return {
                "status": "error",
                "message": response.get("message") or "Order failed"
            }
            
    except Exception as e:
        logger.error(f"Error placing order: {e}")
        return {"status": "error", "message": str(e)}


@router.post("/modifyorder")
async def modify_order(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Modify order (OpenAlgo compatibility)"""
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
    
    auth_service = AuthService(db)
    session = await auth_service.get_session(api_key)
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"status": "error", "code": "AUTH_FAILED", "message": "Invalid API key"}
        )
    
    try:
        broker = await auth_service.get_broker_for_session(session)
        response = await broker.modify_order(body)
        
        if response.get("status"):
            return {
                "status": "success",
                "message": "Order modified successfully",
                "orderid": body.get("orderid")
            }
        else:
             return {
                "status": "error",
                "message": response.get("message") or "Modify failed"
            }
    except Exception as e:
        logger.error(f"Error modifying order: {e}")
        return {"status": "error", "message": str(e)}


@router.post("/cancelorder")
async def cancel_order(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Cancel order (OpenAlgo compatibility)"""
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
    
    auth_service = AuthService(db)
    session = await auth_service.get_session(api_key)
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"status": "error", "code": "AUTH_FAILED", "message": "Invalid API key"}
        )
    
    try:
        broker = await auth_service.get_broker_for_session(session)
        response = await broker.cancel_order(body)
        
        if response.get("status"):
             return {
                "status": "success",
                "message": "Order cancelled successfully",
                "orderid": body.get("orderid")
            }
        else:
             return {
                "status": "error",
                "message": response.get("message") or "Cancel failed"
            }
    except Exception as e:
        logger.error(f"Error cancelling order: {e}")
        return {"status": "error", "message": str(e)}


@router.post("/optiongreeks")
async def get_option_greeks(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Get option Greeks for a single option (OpenAlgo compatibility)"""
    try:
        body = await request.json()
    except Exception:
        body = {}
    
    api_key = body.get("apikey")
    symbol = body.get("symbol")
    exchange = body.get("exchange", "NFO")
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"status": "error", "code": "AUTH_FAILED", "message": "API key required"}
        )
    
    if not symbol:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "code": "INVALID_REQUEST", "message": "Symbol required"}
        )
    
    # Validate API key
    auth_service = AuthService(db)
    session = await auth_service.get_session(api_key)
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"status": "error", "code": "AUTH_FAILED", "message": "Invalid API key"}
        )
    
    try:
        broker = await auth_service.get_broker_for_session(session)
        
        # Get option quote
        quote = await broker.get_quote(symbol, exchange)
        
        # Parse option details from symbol
        from app.api.v1.greeks import _parse_option_symbol
        option_info = _parse_option_symbol(symbol)
        
        if not option_info:
            return {
                "status": "error",
                "message": "Could not parse option symbol"
            }
        
        # Get underlying LTP
        underlying_exchange = "NSE" if exchange == "NFO" else "BSE"
        underlying_quote = await broker.get_quote(option_info["underlying"], underlying_exchange)
        
        # Calculate Greeks
        from app.utils.greeks import calculate_greeks
        greeks = calculate_greeks(
            spot=underlying_quote.ltp,
            strike=option_info["strike"],
            expiry_days=option_info["days_to_expiry"],
            rate=body.get("interest_rate", 0.07),
            option_type=option_info["option_type"],
            option_price=quote.ltp
        )
        
        return {
            "status": "success",
            "symbol": symbol,
            "exchange": exchange,
            "underlying": option_info["underlying"],
            "strike": option_info["strike"],
            "option_type": option_info["option_type"],
            "expiry_date": option_info["expiry"],
            "days_to_expiry": option_info["days_to_expiry"],
            "spot_price": underlying_quote.ltp,
            "option_price": quote.ltp,
            "implied_volatility": greeks.iv,
            "greeks": {
                "delta": greeks.delta,
                "gamma": greeks.gamma,
                "theta": greeks.theta,
                "vega": greeks.vega,
                "rho": 0.0  # Not calculated
            }
        }
        
    except Exception as e:
        logger.error(f"Error calculating Greeks for {symbol}: {e}")
        return {"status": "error", "message": str(e)}


@router.post("/multioptiongreeks")
async def get_multi_option_greeks(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Get option Greeks for multiple options (OpenAlgo compatibility)
    
    Accepts option LTP values directly to avoid rate limiting.
    If LTP is not provided, will attempt to fetch from broker API.
    """
    try:
        body = await request.json()
    except Exception:
        body = {}
    
    api_key = body.get("apikey")
    symbols = body.get("symbols", [])
    interest_rate = body.get("interest_rate", 0.07)
    spot_price = body.get("spot_price")  # Optional: underlying spot price
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"status": "error", "code": "AUTH_FAILED", "message": "API key required"}
        )
    
    if not symbols:
        return {
            "status": "success",
            "data": [],
            "summary": {"total": 0, "success": 0, "failed": 0}
        }
    
    # Validate API key
    auth_service = AuthService(db)
    session = await auth_service.get_session(api_key)
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"status": "error", "code": "AUTH_FAILED", "message": "Invalid API key"}
        )
    
    try:
        broker = await auth_service.get_broker_for_session(session)
        
        results = []
        success_count = 0
        failed_count = 0
        
        # Cache underlying prices
        underlying_prices = {}
        
        from app.api.v1.greeks import _parse_option_symbol
        from app.utils.greeks import calculate_greeks
        
        for sym_info in symbols:
            symbol = sym_info.get("symbol", "")
            exchange = sym_info.get("exchange", "NFO")
            option_ltp = sym_info.get("ltp")  # Accept LTP directly from frontend
            
            try:
                # Parse option details
                option_info = _parse_option_symbol(symbol)
                
                if not option_info:
                    results.append({
                        "symbol": symbol,
                        "status": "error",
                        "error": "Could not parse option symbol"
                    })
                    failed_count += 1
                    continue
                
                # Get underlying price (cached or from request)
                underlying = option_info["underlying"]
                if spot_price and underlying in ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"]:
                    # Use provided spot price for index options
                    spot = spot_price
                elif underlying not in underlying_prices:
                    try:
                        underlying_exchange = "NSE" if exchange == "NFO" else "BSE"
                        underlying_quote = await broker.get_quote(underlying, underlying_exchange)
                        underlying_prices[underlying] = underlying_quote.ltp
                    except Exception as e:
                        logger.warning(f"Could not fetch underlying {underlying}: {e}")
                        # Use a default or skip
                        results.append({
                            "symbol": symbol,
                            "status": "error",
                            "error": f"Could not fetch underlying price: {e}"
                        })
                        failed_count += 1
                        continue
                
                spot = underlying_prices.get(underlying, spot_price or 0)
                
                if spot <= 0:
                    results.append({
                        "symbol": symbol,
                        "status": "error",
                        "error": "No spot price available"
                    })
                    failed_count += 1
                    continue
                
                # Get option LTP - use provided value or fetch
                if option_ltp is not None and option_ltp > 0:
                    ltp = option_ltp
                else:
                    try:
                        quote = await broker.get_quote(symbol, exchange)
                        ltp = quote.ltp
                    except Exception as e:
                        logger.warning(f"Could not fetch quote for {symbol}: {e}")
                        results.append({
                            "symbol": symbol,
                            "status": "error",
                            "error": f"Could not fetch option quote: {e}"
                        })
                        failed_count += 1
                        continue
                
                # Calculate Greeks
                greeks = calculate_greeks(
                    spot=spot,
                    strike=option_info["strike"],
                    expiry_days=option_info["days_to_expiry"],
                    rate=interest_rate,
                    option_type=option_info["option_type"],
                    option_price=ltp
                )
                
                results.append({
                    "symbol": symbol,
                    "exchange": exchange,
                    "status": "success",
                    "underlying": option_info["underlying"],
                    "strike": option_info["strike"],
                    "option_type": option_info["option_type"],
                    "expiry_date": option_info["expiry"],
                    "days_to_expiry": option_info["days_to_expiry"],
                    "spot_price": spot,
                    "option_price": ltp,
                    "implied_volatility": greeks.iv,
                    "greeks": {
                        "delta": greeks.delta,
                        "gamma": greeks.gamma,
                        "theta": greeks.theta,
                        "vega": greeks.vega,
                        "rho": 0.0
                    }
                })
                success_count += 1
                
            except Exception as e:
                results.append({
                    "symbol": symbol,
                    "status": "error",
                    "error": str(e)
                })
                failed_count += 1
        
        return {
            "status": "success",
            "data": results,
            "summary": {
                "total": len(symbols),
                "success": success_count,
                "failed": failed_count
            }
        }
        
    except Exception as e:
        logger.error(f"Error calculating multi Greeks: {e}")
        return {
            "status": "error",
            "message": str(e),
            "data": [],
            "summary": {"total": len(symbols), "success": 0, "failed": len(symbols)}
        }

