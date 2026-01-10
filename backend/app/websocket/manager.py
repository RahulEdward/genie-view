"""
WebSocket Manager
Handles client connections and subscription management
"""

import asyncio
import json
from typing import Dict, Set, Optional, List, Any
from dataclasses import dataclass, field
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect

from app.utils.logger import logger


@dataclass
class ClientConnection:
    """Represents a connected WebSocket client"""
    websocket: WebSocket
    api_key: str
    client_id: str
    subscriptions: Set[str] = field(default_factory=set)
    connected_at: datetime = field(default_factory=datetime.utcnow)
    last_ping: datetime = field(default_factory=datetime.utcnow)


class WebSocketManager:
    """
    Manages WebSocket connections and subscriptions.
    
    Handles:
    - Client connection/disconnection
    - Subscription management (subscribe/unsubscribe)
    - Message routing to subscribed clients
    - Heartbeat/ping-pong
    """
    
    def __init__(self):
        # Map of connection_id -> ClientConnection
        self.connections: Dict[str, ClientConnection] = {}
        
        # Map of symbol_key -> set of connection_ids
        self.subscriptions: Dict[str, Set[str]] = {}
        
        # Lock for thread-safe operations
        self._lock = asyncio.Lock()
        
        # Connection counter for unique IDs
        self._connection_counter = 0
    
    async def connect(
        self,
        websocket: WebSocket,
        api_key: str,
        client_id: str
    ) -> str:
        """
        Accept a new WebSocket connection.
        
        Args:
            websocket: FastAPI WebSocket instance
            api_key: Client's API key
            client_id: Client's broker client ID
        
        Returns:
            Connection ID
        """
        await websocket.accept()
        
        async with self._lock:
            self._connection_counter += 1
            connection_id = f"{client_id}_{self._connection_counter}"
            
            self.connections[connection_id] = ClientConnection(
                websocket=websocket,
                api_key=api_key,
                client_id=client_id
            )
        
        logger.info(f"WebSocket connected: {connection_id}")
        
        # Send welcome message
        await self.send_to_client(connection_id, {
            "type": "connected",
            "connection_id": connection_id,
            "message": "WebSocket connected successfully"
        })
        
        return connection_id
    
    async def disconnect(self, connection_id: str) -> None:
        """
        Handle client disconnection.
        
        Args:
            connection_id: Connection to disconnect
        """
        async with self._lock:
            if connection_id not in self.connections:
                return
            
            client = self.connections[connection_id]
            
            # Remove from all subscriptions
            for symbol_key in list(client.subscriptions):
                if symbol_key in self.subscriptions:
                    self.subscriptions[symbol_key].discard(connection_id)
                    
                    # Clean up empty subscription sets
                    if not self.subscriptions[symbol_key]:
                        del self.subscriptions[symbol_key]
            
            # Remove connection
            del self.connections[connection_id]
        
        logger.info(f"WebSocket disconnected: {connection_id}")
    
    async def subscribe(
        self,
        connection_id: str,
        symbols: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """
        Subscribe to symbols for tick updates.
        
        Args:
            connection_id: Client connection ID
            symbols: List of {symbol, exchange} dicts
        
        Returns:
            Subscription result
        """
        if connection_id not in self.connections:
            return {"success": False, "error": "Connection not found"}
        
        client = self.connections[connection_id]
        subscribed = []
        
        async with self._lock:
            for sym in symbols:
                symbol = sym.get("symbol", "")
                exchange = sym.get("exchange", "NSE")
                symbol_key = f"{exchange}:{symbol}"
                
                # Add to client's subscriptions
                client.subscriptions.add(symbol_key)
                
                # Add to global subscription map
                if symbol_key not in self.subscriptions:
                    self.subscriptions[symbol_key] = set()
                self.subscriptions[symbol_key].add(connection_id)
                
                subscribed.append(symbol_key)
        
        logger.debug(f"Subscribed {connection_id} to {subscribed}")
        
        return {
            "success": True,
            "subscribed": subscribed,
            "total_subscriptions": len(client.subscriptions)
        }
    
    async def unsubscribe(
        self,
        connection_id: str,
        symbols: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """
        Unsubscribe from symbols.
        
        Args:
            connection_id: Client connection ID
            symbols: List of {symbol, exchange} dicts
        
        Returns:
            Unsubscription result
        """
        if connection_id not in self.connections:
            return {"success": False, "error": "Connection not found"}
        
        client = self.connections[connection_id]
        unsubscribed = []
        
        async with self._lock:
            for sym in symbols:
                symbol = sym.get("symbol", "")
                exchange = sym.get("exchange", "NSE")
                symbol_key = f"{exchange}:{symbol}"
                
                # Remove from client's subscriptions
                client.subscriptions.discard(symbol_key)
                
                # Remove from global subscription map
                if symbol_key in self.subscriptions:
                    self.subscriptions[symbol_key].discard(connection_id)
                    
                    if not self.subscriptions[symbol_key]:
                        del self.subscriptions[symbol_key]
                
                unsubscribed.append(symbol_key)
        
        logger.debug(f"Unsubscribed {connection_id} from {unsubscribed}")
        
        return {
            "success": True,
            "unsubscribed": unsubscribed,
            "total_subscriptions": len(client.subscriptions)
        }
    
    async def broadcast_tick(self, symbol_key: str, tick_data: Dict) -> int:
        """
        Broadcast tick data to all subscribed clients.
        
        Args:
            symbol_key: Symbol key (exchange:symbol)
            tick_data: Tick data to broadcast
        
        Returns:
            Number of clients notified
        """
        if symbol_key not in self.subscriptions:
            return 0
        
        connection_ids = list(self.subscriptions[symbol_key])
        sent_count = 0
        
        message = {
            "type": "tick",
            "symbol_key": symbol_key,
            "data": tick_data
        }
        
        for conn_id in connection_ids:
            try:
                await self.send_to_client(conn_id, message)
                sent_count += 1
            except Exception as e:
                logger.warning(f"Failed to send tick to {conn_id}: {e}")
                # Client might be disconnected, clean up
                await self.disconnect(conn_id)
        
        return sent_count
    
    async def send_to_client(
        self,
        connection_id: str,
        message: Dict
    ) -> bool:
        """
        Send message to a specific client.
        
        Args:
            connection_id: Target connection ID
            message: Message to send
        
        Returns:
            True if sent successfully
        """
        if connection_id not in self.connections:
            return False
        
        client = self.connections[connection_id]
        
        try:
            await client.websocket.send_json(message)
            return True
        except Exception as e:
            logger.warning(f"Failed to send to {connection_id}: {e}")
            return False
    
    async def handle_ping(self, connection_id: str) -> None:
        """Handle ping from client"""
        if connection_id in self.connections:
            self.connections[connection_id].last_ping = datetime.utcnow()
            await self.send_to_client(connection_id, {"type": "pong"})
    
    def get_all_subscribed_symbols(self) -> Set[str]:
        """Get all symbols that have at least one subscriber"""
        return set(self.subscriptions.keys())
    
    def get_client_subscriptions(self, connection_id: str) -> Set[str]:
        """Get subscriptions for a specific client"""
        if connection_id in self.connections:
            return self.connections[connection_id].subscriptions.copy()
        return set()
    
    def get_connection_count(self) -> int:
        """Get total number of active connections"""
        return len(self.connections)
    
    def get_subscription_count(self) -> int:
        """Get total number of unique subscriptions"""
        return len(self.subscriptions)
    
    async def cleanup_stale_connections(self, timeout_seconds: int = 60) -> int:
        """
        Remove connections that haven't sent a ping recently.
        
        Args:
            timeout_seconds: Seconds since last ping to consider stale
        
        Returns:
            Number of connections removed
        """
        now = datetime.utcnow()
        stale_connections = []
        
        for conn_id, client in self.connections.items():
            elapsed = (now - client.last_ping).total_seconds()
            if elapsed > timeout_seconds:
                stale_connections.append(conn_id)
        
        for conn_id in stale_connections:
            await self.disconnect(conn_id)
        
        if stale_connections:
            logger.info(f"Cleaned up {len(stale_connections)} stale connections")
        
        return len(stale_connections)


# Global WebSocket manager instance
ws_manager = WebSocketManager()
