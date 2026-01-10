"""
Integration Tests
End-to-end tests for API and WebSocket flows
"""

import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from app.brokers.base import OHLCCandle, Quote


class TestWebSocketIntegration:
    """Integration tests for WebSocket functionality"""
    
    @pytest.mark.asyncio
    async def test_websocket_manager_subscription(self):
        """Test WebSocket subscription management"""
        from app.websocket.manager import WebSocketManager
        
        manager = WebSocketManager()
        
        # Mock WebSocket
        mock_ws = AsyncMock()
        mock_ws.accept = AsyncMock()
        mock_ws.send_json = AsyncMock()
        mock_ws.receive_json = AsyncMock()
        
        client_id = "test_client_1"
        api_key = "test_api_key"
        
        # Connect client - correct signature: websocket, api_key, client_id
        connection_id = await manager.connect(mock_ws, api_key, client_id)
        assert connection_id in manager.connections
        
        # Subscribe to symbol - uses list of dicts
        result = await manager.subscribe(connection_id, [{"symbol": "RELIANCE", "exchange": "NSE"}])
        assert result["success"]
        assert "NSE:RELIANCE" in manager.subscriptions
        assert connection_id in manager.subscriptions["NSE:RELIANCE"]
        
        # Broadcast tick
        tick_data = {"symbol": "RELIANCE", "ltp": 2500.0}
        await manager.broadcast_tick("NSE:RELIANCE", tick_data)
        
        # Verify message sent
        mock_ws.send_json.assert_called()
        
        # Unsubscribe
        await manager.unsubscribe(connection_id, [{"symbol": "RELIANCE", "exchange": "NSE"}])
        assert connection_id not in manager.subscriptions.get("NSE:RELIANCE", set())
        
        # Disconnect
        await manager.disconnect(connection_id)
        assert connection_id not in manager.connections
    
    @pytest.mark.asyncio
    async def test_websocket_multiple_clients(self):
        """Test WebSocket with multiple clients"""
        from app.websocket.manager import WebSocketManager
        
        manager = WebSocketManager()
        
        # Create multiple mock clients
        clients = {}
        connection_ids = []
        for i in range(3):
            mock_ws = AsyncMock()
            mock_ws.accept = AsyncMock()
            mock_ws.send_json = AsyncMock()
            client_id = f"client_{i}"
            api_key = f"api_key_{i}"
            conn_id = await manager.connect(mock_ws, api_key, client_id)
            clients[conn_id] = mock_ws
            connection_ids.append(conn_id)
        
        # Subscribe all to same symbol
        for conn_id in connection_ids:
            await manager.subscribe(conn_id, [{"symbol": "NIFTY", "exchange": "NSE"}])
        
        # Broadcast tick
        tick_data = {"symbol": "NIFTY", "ltp": 20000.0}
        await manager.broadcast_tick("NSE:NIFTY", tick_data)
        
        # All clients should receive
        for conn_id, mock_ws in clients.items():
            mock_ws.send_json.assert_called()
        
        # Cleanup
        for conn_id in list(clients.keys()):
            await manager.disconnect(conn_id)
    
    @pytest.mark.asyncio
    async def test_websocket_client_disconnect_cleanup(self):
        """Test that disconnecting client cleans up subscriptions"""
        from app.websocket.manager import WebSocketManager
        
        manager = WebSocketManager()
        
        mock_ws = AsyncMock()
        mock_ws.accept = AsyncMock()
        mock_ws.send_json = AsyncMock()
        
        client_id = "cleanup_test_client"
        api_key = "test_api_key"
        
        # Connect and subscribe
        connection_id = await manager.connect(mock_ws, api_key, client_id)
        await manager.subscribe(connection_id, [{"symbol": "RELIANCE", "exchange": "NSE"}])
        await manager.subscribe(connection_id, [{"symbol": "TCS", "exchange": "NSE"}])
        
        # Verify subscriptions
        assert connection_id in manager.subscriptions.get("NSE:RELIANCE", set())
        assert connection_id in manager.subscriptions.get("NSE:TCS", set())
        
        # Disconnect
        await manager.disconnect(connection_id)
        
        # Verify cleanup
        assert connection_id not in manager.connections
        assert connection_id not in manager.subscriptions.get("NSE:RELIANCE", set())
        assert connection_id not in manager.subscriptions.get("NSE:TCS", set())


class TestServiceIntegration:
    """Integration tests for service layer"""
    
    @pytest.mark.asyncio
    async def test_market_data_service_deduplication(self):
        """Test that market data service deduplicates candles"""
        from app.services.market_data import MarketDataService
        
        mock_broker = AsyncMock()
        mock_db = AsyncMock()
        
        service = MarketDataService(mock_broker, mock_db)
        
        # Create candles with duplicates
        candles = [
            OHLCCandle(timestamp=1000, open=100, high=101, low=99, close=100.5, volume=1000),
            OHLCCandle(timestamp=1060, open=100.5, high=102, low=100, close=101, volume=1500),
            OHLCCandle(timestamp=1000, open=100.1, high=101.1, low=99.1, close=100.6, volume=1100),  # Duplicate
        ]
        
        result = service._deduplicate_candles(candles)
        
        # Should have 2 unique timestamps
        assert len(result) == 2
        
        # Last occurrence should be kept
        ts_1000_candle = next(c for c in result if c.timestamp == 1000)
        assert ts_1000_candle.close == 100.6  # From the duplicate
    
    @pytest.mark.asyncio
    async def test_option_service_atm_identification(self):
        """Test ATM strike identification"""
        from app.services.option import OptionService
        
        mock_broker = AsyncMock()
        service = OptionService(mock_broker)
        
        options = [
            {"strike": 19800, "option_type": "CE"},
            {"strike": 19900, "option_type": "CE"},
            {"strike": 20000, "option_type": "CE"},
            {"strike": 20100, "option_type": "CE"},
            {"strike": 20200, "option_type": "CE"},
        ]
        
        # Test with spot at 20050
        atm = service.identify_atm_strike(20050, options)
        assert atm == 20000  # Closest to 20050
        
        # Test with spot at 19950
        atm = service.identify_atm_strike(19950, options)
        assert atm == 20000  # Closest to 19950
        
        # Test with spot at 19850
        atm = service.identify_atm_strike(19850, options)
        assert atm == 19800  # Closest to 19850
    
    @pytest.mark.asyncio
    async def test_greeks_calculation_integration(self):
        """Test Greeks calculation with realistic values"""
        from app.utils.greeks import calculate_greeks
        
        # Test call option - using correct parameter names with known volatility
        greeks = calculate_greeks(
            spot=20000,
            strike=20000,
            expiry_days=7,  # 7 days
            rate=0.07,
            option_type="CE",
            volatility=0.15  # Use known volatility instead of calculating IV
        )
        
        # ATM call should have delta around 0.5 (with some tolerance)
        assert 0.45 < greeks.delta < 0.65
        
        # Gamma should be positive
        assert greeks.gamma > 0
        
        # Theta should be negative (time decay)
        assert greeks.theta < 0
        
        # Vega should be positive
        assert greeks.vega > 0
    
    @pytest.mark.asyncio
    async def test_market_timing_service(self):
        """Test market timing service"""
        from app.services.market_timing import MarketTimingService
        
        service = MarketTimingService()
        
        # Get NSE timings - note: this is async
        timings = await service.get_timings("NSE")
        
        assert "pre_open_start" in timings
        assert "market_open" in timings
        assert "market_close" in timings
        
        # Verify reasonable times
        assert timings["market_open"] == "09:15"
        assert timings["market_close"] == "15:30"


class TestCacheIntegration:
    """Integration tests for caching"""
    
    @pytest.mark.asyncio
    async def test_cache_manager_operations(self):
        """Test cache manager basic operations"""
        from app.utils.cache import CacheManager
        
        with patch('app.utils.cache.get_redis') as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis
            
            # Setup mock responses
            mock_redis.get = AsyncMock(return_value='{"key": "value"}')
            mock_redis.setex = AsyncMock(return_value=True)
            mock_redis.delete = AsyncMock(return_value=1)
            
            cache = CacheManager("test")
            
            # Test get
            result = await cache.get("test_key")
            assert result == {"key": "value"}
            
            # Test set with TTL
            await cache.set("test_key", {"new": "data"}, ttl=60)
            mock_redis.setex.assert_called()
            
            # Test delete
            await cache.delete("test_key")
            mock_redis.delete.assert_called()
    
    @pytest.mark.asyncio
    async def test_option_chain_cache_flow(self):
        """Test option chain caching flow"""
        from app.services.option import OptionService
        from app.utils.cache import option_chain_cache
        
        mock_broker = AsyncMock()
        mock_broker.get_option_chain = AsyncMock(return_value={
            "spot_price": 20000,
            "options": [
                {"strike": 20000, "option_type": "CE", "ltp": 100},
                {"strike": 20000, "option_type": "PE", "ltp": 100},
            ]
        })
        
        with patch.object(option_chain_cache, 'get', new_callable=AsyncMock) as mock_get, \
             patch.object(option_chain_cache, 'set', new_callable=AsyncMock) as mock_set:
            
            # First call - cache miss
            mock_get.return_value = None
            
            service = OptionService(mock_broker)
            result = await service.get_option_chain("NIFTY", "NFO")
            
            # Should fetch from broker
            mock_broker.get_option_chain.assert_called_once()
            
            # Should cache result
            mock_set.assert_called_once()
            
            # Verify result structure
            assert result["underlying"] == "NIFTY"
            assert result["spot_price"] == 20000
            assert "calls" in result
            assert "puts" in result


class TestDataTransformation:
    """Integration tests for data transformation"""
    
    @pytest.mark.asyncio
    async def test_ohlc_transformation_preserves_values(self):
        """Test that OHLC transformation preserves all values"""
        from app.brokers.angelone.transformers import transform_candle_data
        
        raw_data = [
            ["2024-01-15T09:15:00+05:30", "100.00", "101.50", "99.50", "100.75", "10000"],
            ["2024-01-15T09:16:00+05:30", "100.75", "102.00", "100.00", "101.25", "15000"],
        ]
        
        candles = transform_candle_data(raw_data)
        
        assert len(candles) == 2
        
        # First candle
        assert candles[0].open == 100.00
        assert candles[0].high == 101.50
        assert candles[0].low == 99.50
        assert candles[0].close == 100.75
        assert candles[0].volume == 10000
        
        # Second candle
        assert candles[1].open == 100.75
        assert candles[1].high == 102.00
        assert candles[1].low == 100.00
        assert candles[1].close == 101.25
        assert candles[1].volume == 15000
    
    @pytest.mark.asyncio
    async def test_price_change_calculation(self):
        """Test price change calculation"""
        from app.services.market_data import calculate_change
        
        # Positive change
        change, pct = calculate_change(105.0, 100.0)
        assert change == 5.0
        assert pct == 5.0
        
        # Negative change
        change, pct = calculate_change(95.0, 100.0)
        assert change == -5.0
        assert pct == -5.0
        
        # Zero prev_close
        change, pct = calculate_change(100.0, 0.0)
        assert change == 0.0
        assert pct == 0.0
