"""
Broker WebSocket Feed
Connects to Angel One WebSocket for real-time tick data
"""

import asyncio
import json
import struct
from typing import Dict, Set, Optional, Callable, Any
from datetime import datetime
import websockets
from websockets.exceptions import ConnectionClosed

from app.brokers.angelone.endpoints import WEBSOCKET_URL, EXCHANGE_TYPE_MAP
from app.utils.logger import logger


class BrokerFeed:
    """
    Manages WebSocket connection to Angel One for real-time market data.
    
    Handles:
    - Connection and authentication
    - Subscription management
    - Tick data parsing
    - Auto-reconnection
    """
    
    def __init__(
        self,
        api_key: str,
        client_id: str,
        feed_token: str,
        on_tick: Optional[Callable[[str, Dict], Any]] = None,
        on_error: Optional[Callable[[str], Any]] = None,
        on_close: Optional[Callable[[], Any]] = None
    ):
        self.api_key = api_key
        self.client_id = client_id
        self.feed_token = feed_token
        
        # Callbacks
        self.on_tick = on_tick
        self.on_error = on_error
        self.on_close = on_close
        
        # Connection state
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._connected = False
        self._running = False
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 5
        self._reconnect_delay = 5  # seconds
        
        # Subscriptions: symbol_key -> token info
        self._subscriptions: Dict[str, Dict] = {}
        
        # Lock for thread-safe operations
        self._lock = asyncio.Lock()
    
    async def connect(self) -> bool:
        """
        Connect to Angel One WebSocket.
        
        Returns:
            True if connected successfully
        """
        try:
            # Build connection URL with auth
            url = f"{WEBSOCKET_URL}?clientCode={self.client_id}&feedToken={self.feed_token}&apiKey={self.api_key}"
            
            self._ws = await websockets.connect(
                url,
                ping_interval=30,
                ping_timeout=10,
                close_timeout=5
            )
            
            self._connected = True
            self._reconnect_attempts = 0
            
            logger.info(f"Broker WebSocket connected for {self.client_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Broker WebSocket connection failed: {e}")
            self._connected = False
            
            if self.on_error:
                await self.on_error(str(e))
            
            return False
    
    async def disconnect(self) -> None:
        """Disconnect from broker WebSocket"""
        self._running = False
        self._connected = False
        
        if self._ws:
            try:
                await self._ws.close()
            except:
                pass
            self._ws = None
        
        logger.info("Broker WebSocket disconnected")
        
        if self.on_close:
            await self.on_close()
    
    async def subscribe(self, symbols: list) -> bool:
        """
        Subscribe to symbols for tick updates.
        
        Args:
            symbols: List of {symbol, exchange, token} dicts
        
        Returns:
            True if subscription sent
        """
        if not self._connected or not self._ws:
            return False
        
        try:
            # Group by exchange
            exchange_tokens: Dict[int, list] = {}
            
            for sym in symbols:
                exchange = sym.get("exchange", "NSE")
                token = sym.get("token", "")
                symbol = sym.get("symbol", "")
                
                exchange_type = EXCHANGE_TYPE_MAP.get(exchange, 1)
                
                if exchange_type not in exchange_tokens:
                    exchange_tokens[exchange_type] = []
                
                exchange_tokens[exchange_type].append(token)
                
                # Store subscription
                symbol_key = f"{exchange}:{symbol}"
                self._subscriptions[symbol_key] = {
                    "token": token,
                    "exchange": exchange,
                    "exchange_type": exchange_type
                }
            
            # Build subscription request
            # Angel One format: {"correlationID": "...", "action": 1, "params": {"mode": 3, "tokenList": [{"exchangeType": 1, "tokens": ["2885"]}]}}
            token_list = [
                {"exchangeType": ex_type, "tokens": tokens}
                for ex_type, tokens in exchange_tokens.items()
            ]
            
            request = {
                "correlationID": f"sub_{datetime.utcnow().timestamp()}",
                "action": 1,  # Subscribe
                "params": {
                    "mode": 3,  # Full mode (LTP + Quote + Depth)
                    "tokenList": token_list
                }
            }
            
            await self._ws.send(json.dumps(request))
            
            logger.debug(f"Subscribed to {len(symbols)} symbols")
            
            return True
            
        except Exception as e:
            logger.error(f"Subscription failed: {e}")
            return False
    
    async def unsubscribe(self, symbols: list) -> bool:
        """
        Unsubscribe from symbols.
        
        Args:
            symbols: List of {symbol, exchange, token} dicts
        
        Returns:
            True if unsubscription sent
        """
        if not self._connected or not self._ws:
            return False
        
        try:
            # Group by exchange
            exchange_tokens: Dict[int, list] = {}
            
            for sym in symbols:
                exchange = sym.get("exchange", "NSE")
                token = sym.get("token", "")
                symbol = sym.get("symbol", "")
                
                exchange_type = EXCHANGE_TYPE_MAP.get(exchange, 1)
                
                if exchange_type not in exchange_tokens:
                    exchange_tokens[exchange_type] = []
                
                exchange_tokens[exchange_type].append(token)
                
                # Remove subscription
                symbol_key = f"{exchange}:{symbol}"
                self._subscriptions.pop(symbol_key, None)
            
            # Build unsubscription request
            token_list = [
                {"exchangeType": ex_type, "tokens": tokens}
                for ex_type, tokens in exchange_tokens.items()
            ]
            
            request = {
                "correlationID": f"unsub_{datetime.utcnow().timestamp()}",
                "action": 0,  # Unsubscribe
                "params": {
                    "mode": 3,
                    "tokenList": token_list
                }
            }
            
            await self._ws.send(json.dumps(request))
            
            logger.debug(f"Unsubscribed from {len(symbols)} symbols")
            
            return True
            
        except Exception as e:
            logger.error(f"Unsubscription failed: {e}")
            return False
    
    async def run(self) -> None:
        """
        Main loop to receive and process messages.
        
        Runs until disconnect() is called.
        """
        self._running = True
        
        while self._running:
            try:
                if not self._connected:
                    connected = await self.connect()
                    if not connected:
                        await self._handle_reconnect()
                        continue
                
                # Receive message
                message = await self._ws.recv()
                
                # Parse and process
                await self._process_message(message)
                
            except ConnectionClosed as e:
                logger.warning(f"Broker WebSocket closed: {e}")
                self._connected = False
                
                if self._running:
                    await self._handle_reconnect()
                    
            except Exception as e:
                logger.error(f"Broker WebSocket error: {e}")
                
                if self.on_error:
                    await self.on_error(str(e))
    
    async def _process_message(self, message: bytes) -> None:
        """Process incoming WebSocket message"""
        try:
            # Angel One sends binary data
            if isinstance(message, bytes):
                tick = self._parse_binary_tick(message)
                if tick and self.on_tick:
                    symbol_key = tick.get("symbol_key", "")
                    await self.on_tick(symbol_key, tick)
            else:
                # JSON message (acknowledgments, errors)
                data = json.loads(message)
                logger.debug(f"Broker message: {data}")
                
        except Exception as e:
            logger.warning(f"Failed to process message: {e}")
    
    def _parse_binary_tick(self, data: bytes) -> Optional[Dict]:
        """
        Parse binary tick data from Angel One.
        
        Binary format varies by subscription mode.
        Mode 3 (Full): Token(4) + Seq(8) + ExchTime(8) + LTP(4) + ...
        """
        try:
            if len(data) < 20:
                return None
            
            # Parse header
            subscription_mode = data[0]
            exchange_type = data[1]
            
            # Parse token (bytes 2-5)
            token = str(struct.unpack('<I', data[2:6])[0])
            
            # Find symbol key from token
            symbol_key = self._find_symbol_by_token(token, exchange_type)
            
            if not symbol_key:
                return None
            
            # Parse based on mode
            if subscription_mode == 1:  # LTP mode
                ltp = struct.unpack('<I', data[6:10])[0] / 100
                return {
                    "symbol_key": symbol_key,
                    "ltp": ltp,
                    "timestamp": datetime.utcnow().isoformat()
                }
            
            elif subscription_mode == 2:  # Quote mode
                ltp = struct.unpack('<I', data[6:10])[0] / 100
                last_qty = struct.unpack('<I', data[10:14])[0]
                avg_price = struct.unpack('<I', data[14:18])[0] / 100
                volume = struct.unpack('<I', data[18:22])[0]
                
                return {
                    "symbol_key": symbol_key,
                    "ltp": ltp,
                    "last_qty": last_qty,
                    "avg_price": avg_price,
                    "volume": volume,
                    "timestamp": datetime.utcnow().isoformat()
                }
            
            elif subscription_mode == 3:  # Full mode
                ltp = struct.unpack('<I', data[6:10])[0] / 100
                last_qty = struct.unpack('<I', data[10:14])[0]
                avg_price = struct.unpack('<I', data[14:18])[0] / 100
                volume = struct.unpack('<I', data[18:22])[0]
                total_buy_qty = struct.unpack('<Q', data[22:30])[0]
                total_sell_qty = struct.unpack('<Q', data[30:38])[0]
                open_price = struct.unpack('<I', data[38:42])[0] / 100
                high_price = struct.unpack('<I', data[42:46])[0] / 100
                low_price = struct.unpack('<I', data[46:50])[0] / 100
                close_price = struct.unpack('<I', data[50:54])[0] / 100
                
                return {
                    "symbol_key": symbol_key,
                    "ltp": ltp,
                    "last_qty": last_qty,
                    "avg_price": avg_price,
                    "volume": volume,
                    "total_buy_qty": total_buy_qty,
                    "total_sell_qty": total_sell_qty,
                    "open": open_price,
                    "high": high_price,
                    "low": low_price,
                    "close": close_price,
                    "timestamp": datetime.utcnow().isoformat()
                }
            
            return None
            
        except Exception as e:
            logger.warning(f"Failed to parse binary tick: {e}")
            return None
    
    def _find_symbol_by_token(self, token: str, exchange_type: int) -> Optional[str]:
        """Find symbol key by token and exchange type"""
        for symbol_key, info in self._subscriptions.items():
            if info["token"] == token and info["exchange_type"] == exchange_type:
                return symbol_key
        return None
    
    async def _handle_reconnect(self) -> None:
        """Handle reconnection with exponential backoff"""
        self._reconnect_attempts += 1
        
        if self._reconnect_attempts > self._max_reconnect_attempts:
            logger.error("Max reconnection attempts reached")
            self._running = False
            
            if self.on_close:
                await self.on_close()
            return
        
        delay = self._reconnect_delay * (2 ** (self._reconnect_attempts - 1))
        logger.info(f"Reconnecting in {delay} seconds (attempt {self._reconnect_attempts})")
        
        await asyncio.sleep(delay)
    
    @property
    def is_connected(self) -> bool:
        """Check if connected to broker WebSocket"""
        return self._connected
    
    @property
    def subscription_count(self) -> int:
        """Get number of active subscriptions"""
        return len(self._subscriptions)


# Global broker feed instance (initialized per session)
_broker_feeds: Dict[str, BrokerFeed] = {}


async def get_or_create_feed(
    client_id: str,
    api_key: str,
    feed_token: str,
    on_tick: Optional[Callable] = None
) -> BrokerFeed:
    """Get existing or create new broker feed for a client"""
    if client_id in _broker_feeds:
        return _broker_feeds[client_id]
    
    feed = BrokerFeed(
        api_key=api_key,
        client_id=client_id,
        feed_token=feed_token,
        on_tick=on_tick
    )
    
    _broker_feeds[client_id] = feed
    return feed


async def remove_feed(client_id: str) -> None:
    """Remove and disconnect broker feed"""
    if client_id in _broker_feeds:
        feed = _broker_feeds.pop(client_id)
        await feed.disconnect()
