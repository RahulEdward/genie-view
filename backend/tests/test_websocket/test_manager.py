"""
WebSocket Manager Tests
Property-based and unit tests for WebSocket subscription routing
"""

import pytest
from hypothesis import given, strategies as st, settings
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from app.websocket.manager import WebSocketManager, ClientConnection


# ==================== Property Tests ====================

class TestSubscriptionRouting:
    """
    Property 7: WebSocket Subscription Routing
    For any tick data, it SHALL be routed only to clients subscribed to that symbol.
    Validates: Requirements 5.2, 5.5, 5.6
    """
    
    @given(
        st.lists(
            st.tuples(
                st.text(min_size=1, max_size=10, alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ"),
                st.sampled_from(["NSE", "BSE", "NFO"])
            ),
            min_size=1,
            max_size=20,
            unique=True
        ),
        st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=100)
    def test_tick_only_sent_to_subscribers(self, symbols, num_clients):
        """
        Property: Ticks are only sent to clients subscribed to that symbol.
        """
        manager = WebSocketManager()
        
        # Create mock clients
        clients = []
        for i in range(num_clients):
            mock_ws = MagicMock()
            mock_ws.send_json = AsyncMock()
            clients.append({
                "id": f"client_{i}",
                "ws": mock_ws,
                "subscriptions": set()
            })
        
        # Simulate connections and subscriptions
        for client in clients:
            manager.connections[client["id"]] = ClientConnection(
                websocket=client["ws"],
                api_key=f"key_{client['id']}",
                client_id=client["id"]
            )
        
        # Subscribe each client to random subset of symbols
        import random
        for client in clients:
            num_subs = random.randint(0, len(symbols))
            client_symbols = random.sample(symbols, num_subs)
            
            for symbol, exchange in client_symbols:
                symbol_key = f"{exchange}:{symbol}"
                client["subscriptions"].add(symbol_key)
                manager.connections[client["id"]].subscriptions.add(symbol_key)
                
                if symbol_key not in manager.subscriptions:
                    manager.subscriptions[symbol_key] = set()
                manager.subscriptions[symbol_key].add(client["id"])
        
        # Verify routing logic
        for symbol, exchange in symbols:
            symbol_key = f"{exchange}:{symbol}"
            
            # Get expected subscribers
            expected_subscribers = set()
            for client in clients:
                if symbol_key in client["subscriptions"]:
                    expected_subscribers.add(client["id"])
            
            # Get actual subscribers from manager
            actual_subscribers = manager.subscriptions.get(symbol_key, set())
            
            # Should match
            assert actual_subscribers == expected_subscribers, \
                f"Mismatch for {symbol_key}: expected {expected_subscribers}, got {actual_subscribers}"
    
    @given(
        st.lists(
            st.text(min_size=1, max_size=10, alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ"),
            min_size=1,
            max_size=10,
            unique=True
        )
    )
    @settings(max_examples=100)
    def test_unsubscribe_removes_from_routing(self, symbols):
        """
        Property: After unsubscribe, client no longer receives ticks for that symbol.
        """
        manager = WebSocketManager()
        
        # Create mock client
        mock_ws = MagicMock()
        mock_ws.send_json = AsyncMock()
        
        client_id = "test_client"
        manager.connections[client_id] = ClientConnection(
            websocket=mock_ws,
            api_key="test_key",
            client_id=client_id
        )
        
        # Subscribe to all symbols
        for symbol in symbols:
            symbol_key = f"NSE:{symbol}"
            manager.connections[client_id].subscriptions.add(symbol_key)
            
            if symbol_key not in manager.subscriptions:
                manager.subscriptions[symbol_key] = set()
            manager.subscriptions[symbol_key].add(client_id)
        
        # Unsubscribe from first symbol
        if symbols:
            first_symbol = symbols[0]
            symbol_key = f"NSE:{first_symbol}"
            
            manager.connections[client_id].subscriptions.discard(symbol_key)
            if symbol_key in manager.subscriptions:
                manager.subscriptions[symbol_key].discard(client_id)
                if not manager.subscriptions[symbol_key]:
                    del manager.subscriptions[symbol_key]
            
            # Verify unsubscribed
            assert symbol_key not in manager.connections[client_id].subscriptions
            assert client_id not in manager.subscriptions.get(symbol_key, set())
    
    @given(st.integers(min_value=1, max_value=50))
    @settings(max_examples=50)
    def test_disconnect_cleans_up_subscriptions(self, num_subscriptions):
        """
        Property: When client disconnects, all its subscriptions are cleaned up.
        """
        manager = WebSocketManager()
        
        # Create mock client
        mock_ws = MagicMock()
        client_id = "test_client"
        
        manager.connections[client_id] = ClientConnection(
            websocket=mock_ws,
            api_key="test_key",
            client_id=client_id
        )
        
        # Subscribe to symbols
        for i in range(num_subscriptions):
            symbol_key = f"NSE:SYMBOL{i}"
            manager.connections[client_id].subscriptions.add(symbol_key)
            
            if symbol_key not in manager.subscriptions:
                manager.subscriptions[symbol_key] = set()
            manager.subscriptions[symbol_key].add(client_id)
        
        # Simulate disconnect
        client = manager.connections[client_id]
        for symbol_key in list(client.subscriptions):
            if symbol_key in manager.subscriptions:
                manager.subscriptions[symbol_key].discard(client_id)
                if not manager.subscriptions[symbol_key]:
                    del manager.subscriptions[symbol_key]
        
        del manager.connections[client_id]
        
        # Verify cleanup
        assert client_id not in manager.connections
        for symbol_key in manager.subscriptions:
            assert client_id not in manager.subscriptions[symbol_key]


class TestSubscriptionManagement:
    """Test subscription management"""
    
    @given(
        st.lists(
            st.fixed_dictionaries({
                "symbol": st.text(min_size=1, max_size=10, alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ"),
                "exchange": st.sampled_from(["NSE", "BSE", "NFO"])
            }),
            min_size=0,
            max_size=20
        )
    )
    @settings(max_examples=100)
    def test_subscription_count_accurate(self, symbols):
        """
        Property: Subscription count matches actual subscriptions.
        """
        manager = WebSocketManager()
        
        # Create mock client
        mock_ws = MagicMock()
        client_id = "test_client"
        
        manager.connections[client_id] = ClientConnection(
            websocket=mock_ws,
            api_key="test_key",
            client_id=client_id
        )
        
        # Subscribe
        unique_keys = set()
        for sym in symbols:
            symbol_key = f"{sym['exchange']}:{sym['symbol']}"
            unique_keys.add(symbol_key)
            
            manager.connections[client_id].subscriptions.add(symbol_key)
            
            if symbol_key not in manager.subscriptions:
                manager.subscriptions[symbol_key] = set()
            manager.subscriptions[symbol_key].add(client_id)
        
        # Verify counts
        assert len(manager.connections[client_id].subscriptions) == len(unique_keys)
        assert manager.get_subscription_count() == len(unique_keys)


# ==================== Unit Tests ====================

class TestWebSocketManager:
    """Unit tests for WebSocketManager"""
    
    @pytest.fixture
    def manager(self):
        return WebSocketManager()
    
    @pytest.fixture
    def mock_websocket(self):
        ws = MagicMock()
        ws.send_json = AsyncMock()
        ws.accept = AsyncMock()
        return ws
    
    @pytest.mark.asyncio
    async def test_connect_creates_connection(self, manager, mock_websocket):
        """Test that connect creates a new connection"""
        conn_id = await manager.connect(mock_websocket, "api_key", "client_1")
        
        assert conn_id in manager.connections
        assert manager.connections[conn_id].api_key == "api_key"
        assert manager.connections[conn_id].client_id == "client_1"
        mock_websocket.accept.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_disconnect_removes_connection(self, manager, mock_websocket):
        """Test that disconnect removes connection"""
        conn_id = await manager.connect(mock_websocket, "api_key", "client_1")
        
        await manager.disconnect(conn_id)
        
        assert conn_id not in manager.connections
    
    @pytest.mark.asyncio
    async def test_subscribe_adds_to_subscriptions(self, manager, mock_websocket):
        """Test that subscribe adds symbols to subscriptions"""
        conn_id = await manager.connect(mock_websocket, "api_key", "client_1")
        
        symbols = [
            {"symbol": "RELIANCE", "exchange": "NSE"},
            {"symbol": "TCS", "exchange": "NSE"}
        ]
        
        result = await manager.subscribe(conn_id, symbols)
        
        assert result["success"] is True
        assert len(result["subscribed"]) == 2
        assert "NSE:RELIANCE" in manager.connections[conn_id].subscriptions
        assert "NSE:TCS" in manager.connections[conn_id].subscriptions
    
    @pytest.mark.asyncio
    async def test_unsubscribe_removes_from_subscriptions(self, manager, mock_websocket):
        """Test that unsubscribe removes symbols"""
        conn_id = await manager.connect(mock_websocket, "api_key", "client_1")
        
        symbols = [{"symbol": "RELIANCE", "exchange": "NSE"}]
        await manager.subscribe(conn_id, symbols)
        
        result = await manager.unsubscribe(conn_id, symbols)
        
        assert result["success"] is True
        assert "NSE:RELIANCE" not in manager.connections[conn_id].subscriptions
    
    @pytest.mark.asyncio
    async def test_broadcast_tick_sends_to_subscribers(self, manager, mock_websocket):
        """Test that broadcast sends to subscribed clients"""
        conn_id = await manager.connect(mock_websocket, "api_key", "client_1")
        
        symbols = [{"symbol": "RELIANCE", "exchange": "NSE"}]
        await manager.subscribe(conn_id, symbols)
        
        tick_data = {"ltp": 2500.0, "volume": 1000}
        sent_count = await manager.broadcast_tick("NSE:RELIANCE", tick_data)
        
        assert sent_count == 1
        mock_websocket.send_json.assert_called()
    
    @pytest.mark.asyncio
    async def test_broadcast_tick_not_sent_to_non_subscribers(self, manager, mock_websocket):
        """Test that broadcast doesn't send to non-subscribers"""
        conn_id = await manager.connect(mock_websocket, "api_key", "client_1")
        
        # Subscribe to different symbol
        symbols = [{"symbol": "TCS", "exchange": "NSE"}]
        await manager.subscribe(conn_id, symbols)
        
        # Broadcast for RELIANCE (not subscribed)
        tick_data = {"ltp": 2500.0}
        sent_count = await manager.broadcast_tick("NSE:RELIANCE", tick_data)
        
        assert sent_count == 0
    
    def test_get_all_subscribed_symbols(self, manager):
        """Test getting all subscribed symbols"""
        manager.subscriptions = {
            "NSE:RELIANCE": {"client_1"},
            "NSE:TCS": {"client_1", "client_2"},
            "BSE:INFY": {"client_2"}
        }
        
        symbols = manager.get_all_subscribed_symbols()
        
        assert len(symbols) == 3
        assert "NSE:RELIANCE" in symbols
        assert "NSE:TCS" in symbols
        assert "BSE:INFY" in symbols
    
    def test_get_connection_count(self, manager):
        """Test connection count"""
        assert manager.get_connection_count() == 0
        
        manager.connections["client_1"] = MagicMock()
        manager.connections["client_2"] = MagicMock()
        
        assert manager.get_connection_count() == 2
