"""
WebSocket Endpoint
Real-time tick data streaming
"""

import asyncio
import json
from typing import Optional, List, Dict
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.auth import AuthService
from app.websocket.manager import ws_manager
from app.websocket.broker_feed import get_or_create_feed, remove_feed
from app.brokers.factory import get_broker
from app.brokers.angelone.endpoints import INDEX_SYMBOLS
from app.utils.logger import logger

router = APIRouter()


async def lookup_symbol_tokens(
    symbols: List[Dict],
    broker_name: str,
    broker_api_key: str,
    jwt_token: str,
    client_id: str
) -> List[Dict]:
    """
    Look up symbol tokens for subscription.
    Returns symbols with tokens filled in.
    """
    result = []
    
    # Get broker adapter
    broker = get_broker(broker_name, broker_api_key)
    broker.set_tokens(
        jwt_token=jwt_token,
        refresh_token="",
        feed_token="",
        client_id=client_id
    )
    
    for sym in symbols:
        symbol = sym.get("symbol", "")
        exchange = sym.get("exchange", "NSE")
        token = sym.get("token", "")
        
        # If token not provided, look it up
        if not token:
            # Check index symbols first
            if symbol in INDEX_SYMBOLS:
                token = INDEX_SYMBOLS[symbol]["token"]
            else:
                # Search for token
                try:
                    token = await broker.get_symbol_token(symbol, exchange)
                except Exception as e:
                    logger.warning(f"Failed to get token for {symbol}: {e}")
        
        if token:
            result.append({
                "symbol": symbol,
                "exchange": exchange,
                "token": token
            })
        else:
            logger.warning(f"No token found for {symbol}:{exchange}")
    
    return result


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    apikey: str = Query(..., description="API key from login")
):
    """
    WebSocket endpoint for real-time tick data.
    
    Connect with: ws://host/ws?apikey=YOUR_API_KEY
    
    Messages:
    - Subscribe: {"action": "subscribe", "symbols": [{"symbol": "RELIANCE", "exchange": "NSE", "token": "2885"}]}
    - Unsubscribe: {"action": "unsubscribe", "symbols": [{"symbol": "RELIANCE", "exchange": "NSE"}]}
    - Ping: {"action": "ping"}
    
    Responses:
    - Connected: {"type": "connected", "connection_id": "..."}
    - Tick: {"type": "tick", "symbol_key": "NSE:RELIANCE", "data": {...}}
    - Pong: {"type": "pong"}
    - Error: {"type": "error", "message": "..."}
    """
    connection_id = None
    broker_feed = None
    user_session = None
    
    try:
        # Validate API key
        db = get_db_session()
        async with db as session:
            auth_service = AuthService(session)
            user_session = await auth_service.get_session(apikey)
            
            if not user_session:
                await websocket.close(code=4001, reason="Invalid API key")
                return
            
            client_id = user_session.client_id
            feed_token = user_session.feed_token
            broker_api_key = user_session.broker_api_key  # Use broker API key for WebSocket
            broker_name = user_session.broker
        
        # Connect client
        connection_id = await ws_manager.connect(websocket, apikey, client_id)
        
        # Create tick callback
        async def on_tick(symbol_key: str, tick_data: dict):
            await ws_manager.broadcast_tick(symbol_key, tick_data)
        
        # Get or create broker feed
        broker_feed = await get_or_create_feed(
            client_id=client_id,
            api_key=broker_api_key,
            feed_token=feed_token,
            on_tick=on_tick
        )
        
        # Connect broker feed if not connected
        if not broker_feed.is_connected:
            connected = await broker_feed.connect()
            if connected and not broker_feed.is_running:
                # Start feed in background only if not already running
                asyncio.create_task(broker_feed.run())
        
        # Message handling loop
        while True:
            try:
                # Receive message
                data = await websocket.receive_text()
                message = json.loads(data)
                
                action = message.get("action", "")
                
                if action == "ping":
                    await ws_manager.handle_ping(connection_id)
                
                elif action == "authenticate":
                    # Frontend sends authenticate after connect - already authenticated via query param
                    # Just send success response
                    await ws_manager.send_to_client(connection_id, {
                        "type": "auth",
                        "status": "success",
                        "message": "Authenticated successfully",
                        "broker": broker_name
                    })
                
                elif action == "subscribe":
                    # Handle both single symbol and array formats
                    symbols = message.get("symbols", [])
                    
                    # Frontend sends single symbol format: {symbol, exchange, mode}
                    if not symbols and message.get("symbol"):
                        symbols = [{
                            "symbol": message.get("symbol"),
                            "exchange": message.get("exchange", "NSE"),
                            "token": message.get("token", "")
                        }]
                    
                    # Look up tokens for symbols that don't have them
                    if symbols and broker_api_key:
                        symbols_with_tokens = await lookup_symbol_tokens(
                            symbols,
                            broker_name,
                            broker_api_key,
                            user_session.jwt_token,
                            client_id
                        )
                    else:
                        symbols_with_tokens = symbols
                    
                    # Subscribe in manager
                    result = await ws_manager.subscribe(connection_id, symbols_with_tokens)
                    
                    # Subscribe in broker feed
                    if broker_feed and symbols_with_tokens:
                        await broker_feed.subscribe(symbols_with_tokens)
                    
                    await ws_manager.send_to_client(connection_id, {
                        "type": "subscribed",
                        **result
                    })
                
                elif action == "unsubscribe":
                    # Handle both single symbol and array formats
                    symbols = message.get("symbols", [])
                    
                    # Frontend sends single symbol format: {symbol, exchange}
                    if not symbols and message.get("symbol"):
                        symbols = [{
                            "symbol": message.get("symbol"),
                            "exchange": message.get("exchange", "NSE")
                        }]
                    
                    # Unsubscribe in manager
                    result = await ws_manager.unsubscribe(connection_id, symbols)
                    
                    # Check if any other clients still need these symbols
                    # Only unsubscribe from broker if no one else needs them
                    for sym in symbols:
                        symbol_key = f"{sym.get('exchange', 'NSE')}:{sym.get('symbol', '')}"
                        if symbol_key not in ws_manager.subscriptions:
                            if broker_feed:
                                await broker_feed.unsubscribe([sym])
                    
                    await ws_manager.send_to_client(connection_id, {
                        "type": "unsubscribed",
                        **result
                    })
                
                else:
                    await ws_manager.send_to_client(connection_id, {
                        "type": "error",
                        "message": f"Unknown action: {action}"
                    })
                    
            except json.JSONDecodeError:
                await ws_manager.send_to_client(connection_id, {
                    "type": "error",
                    "message": "Invalid JSON message"
                })
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {connection_id}")
        
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        
    finally:
        # Cleanup
        if connection_id:
            await ws_manager.disconnect(connection_id)
        
        # Check if broker feed should be closed
        # (only if no other connections for this client)
        if broker_feed and ws_manager.get_connection_count() == 0:
            await remove_feed(client_id)


def get_db_session():
    """Get database session for WebSocket"""
    from app.db.session import async_session_maker
    return async_session_maker()


# Background task for cleanup
async def cleanup_task():
    """Periodic cleanup of stale connections"""
    while True:
        await asyncio.sleep(60)  # Run every minute
        await ws_manager.cleanup_stale_connections(timeout_seconds=120)


# Start cleanup task on module load
_cleanup_task: Optional[asyncio.Task] = None


def start_cleanup_task():
    """Start the cleanup background task"""
    global _cleanup_task
    if _cleanup_task is None:
        _cleanup_task = asyncio.create_task(cleanup_task())


def stop_cleanup_task():
    """Stop the cleanup background task"""
    global _cleanup_task
    if _cleanup_task:
        _cleanup_task.cancel()
        _cleanup_task = None
