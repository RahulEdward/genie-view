"""
Database Operations Tests
Property tests for OHLC storage and cache TTL
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from hypothesis import given, strategies as st, settings as hyp_settings

from app.services.market_data import MarketDataService
from app.brokers.base import OHLCCandle


# Strategy for generating OHLC candles
@st.composite
def ohlc_candle_strategy(draw):
    """Generate valid OHLC candles"""
    base_price = draw(st.floats(min_value=100, max_value=50000, allow_nan=False, allow_infinity=False))
    variation = draw(st.floats(min_value=0.001, max_value=0.05, allow_nan=False, allow_infinity=False))
    
    open_price = base_price
    high_price = base_price * (1 + variation)
    low_price = base_price * (1 - variation)
    close_price = draw(st.floats(min_value=low_price, max_value=high_price, allow_nan=False, allow_infinity=False))
    
    # Generate timestamp within reasonable range
    base_ts = int(datetime(2024, 1, 1).timestamp())
    timestamp = draw(st.integers(min_value=base_ts, max_value=base_ts + 86400 * 365))
    
    volume = draw(st.integers(min_value=0, max_value=10000000))
    
    return OHLCCandle(
        timestamp=timestamp,
        open=round(open_price, 2),
        high=round(high_price, 2),
        low=round(low_price, 2),
        close=round(close_price, 2),
        volume=volume
    )


@st.composite
def duplicate_candles_strategy(draw):
    """Generate list of candles with intentional duplicates"""
    # Generate base candles
    num_unique = draw(st.integers(min_value=1, max_value=10))
    candles = []
    
    base_ts = int(datetime(2024, 1, 1, 9, 15).timestamp())
    
    for i in range(num_unique):
        base_price = draw(st.floats(min_value=100, max_value=50000, allow_nan=False, allow_infinity=False))
        variation = draw(st.floats(min_value=0.001, max_value=0.05, allow_nan=False, allow_infinity=False))
        
        candle = OHLCCandle(
            timestamp=base_ts + (i * 60),  # 1 minute apart
            open=round(base_price, 2),
            high=round(base_price * (1 + variation), 2),
            low=round(base_price * (1 - variation), 2),
            close=round(base_price * (1 + variation / 2), 2),
            volume=draw(st.integers(min_value=0, max_value=1000000))
        )
        candles.append(candle)
    
    # Add duplicates (same timestamp, different values)
    num_duplicates = draw(st.integers(min_value=0, max_value=min(5, num_unique)))
    for _ in range(num_duplicates):
        if candles:
            original = draw(st.sampled_from(candles))
            # Create duplicate with same timestamp but potentially different values
            duplicate = OHLCCandle(
                timestamp=original.timestamp,
                open=original.open + draw(st.floats(min_value=-1, max_value=1, allow_nan=False, allow_infinity=False)),
                high=original.high,
                low=original.low,
                close=original.close,
                volume=original.volume + draw(st.integers(min_value=0, max_value=100))
            )
            candles.append(duplicate)
    
    return candles


class TestDuplicateHandling:
    """Property 13: Database Duplicate Handling"""
    
    @given(candles=duplicate_candles_strategy())
    @hyp_settings(max_examples=50, deadline=None)
    @pytest.mark.asyncio
    async def test_duplicate_candles_no_error(self, candles):
        """
        Property: Storing duplicate candles should not raise errors.
        Duplicates should be handled gracefully via upsert.
        """
        # Mock database session
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        
        # Mock broker
        mock_broker = AsyncMock()
        
        service = MarketDataService(mock_broker, mock_db)
        
        # Should not raise any exception
        try:
            await service._store_candles("RELIANCE", "NSE", "1m", candles)
            success = True
        except Exception as e:
            success = False
            pytest.fail(f"Duplicate handling failed: {e}")
        
        assert success, "Storing candles with duplicates should succeed"
    
    @given(candles=duplicate_candles_strategy())
    @hyp_settings(max_examples=50, deadline=None)
    @pytest.mark.asyncio
    async def test_deduplicate_keeps_last(self, candles):
        """
        Property: Deduplication should keep the last occurrence of each timestamp.
        """
        mock_db = AsyncMock()
        mock_broker = AsyncMock()
        
        service = MarketDataService(mock_broker, mock_db)
        
        # Test deduplication
        result = service._deduplicate_candles(candles)
        
        # All timestamps should be unique
        timestamps = [c.timestamp for c in result]
        assert len(timestamps) == len(set(timestamps)), "Deduplicated candles should have unique timestamps"
        
        # For each timestamp, the last occurrence should be kept
        timestamp_to_last = {}
        for candle in candles:
            timestamp_to_last[candle.timestamp] = candle
        
        for candle in result:
            expected = timestamp_to_last[candle.timestamp]
            assert candle.timestamp == expected.timestamp
            assert candle.close == expected.close
    
    @given(candle=ohlc_candle_strategy())
    @hyp_settings(max_examples=30, deadline=None)
    @pytest.mark.asyncio
    async def test_upsert_updates_existing(self, candle):
        """
        Property: Storing a candle with existing timestamp should update, not insert.
        """
        # Mock existing row
        existing_row = MagicMock()
        existing_row.open = candle.open - 1
        existing_row.high = candle.high - 1
        existing_row.low = candle.low + 1
        existing_row.close = candle.close - 1
        existing_row.volume = candle.volume - 100
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=existing_row)
        
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()
        
        mock_broker = AsyncMock()
        
        service = MarketDataService(mock_broker, mock_db)
        
        await service._store_candles("RELIANCE", "NSE", "1m", [candle])
        
        # Verify existing row was updated
        assert existing_row.open == candle.open
        assert existing_row.high == candle.high
        assert existing_row.low == candle.low
        assert existing_row.close == candle.close
        assert existing_row.volume == candle.volume


class TestCacheTTLExpiration:
    """Property 14: Cache TTL Expiration"""
    
    @given(ttl_seconds=st.integers(min_value=1, max_value=300))
    @hyp_settings(max_examples=20, deadline=None)
    @pytest.mark.asyncio
    async def test_cache_respects_ttl(self, ttl_seconds):
        """
        Property: Cached data should expire after TTL.
        """
        from app.utils.cache import CacheManager
        
        with patch('app.utils.cache.get_redis') as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis
            
            # Setup mock to track setex calls
            mock_redis.setex = AsyncMock(return_value=True)
            mock_redis.get = AsyncMock(return_value=None)
            
            cache = CacheManager("test")
            
            # Set with TTL
            await cache.set("key", {"data": "value"}, ttl=ttl_seconds)
            
            # Verify setex was called with correct TTL
            mock_redis.setex.assert_called_once()
            call_args = mock_redis.setex.call_args
            assert call_args[0][1] == ttl_seconds, f"TTL should be {ttl_seconds}"
    
    @pytest.mark.asyncio
    async def test_expired_cache_returns_none(self):
        """
        Property: Expired cache should return None, triggering fresh fetch.
        """
        from app.utils.cache import CacheManager
        
        with patch('app.utils.cache.get_redis') as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis
            
            # Simulate expired key (returns None)
            mock_redis.get = AsyncMock(return_value=None)
            
            cache = CacheManager("test")
            result = await cache.get("expired_key")
            
            assert result is None, "Expired cache should return None"
    
    @given(
        underlying=st.sampled_from(["NIFTY", "BANKNIFTY", "RELIANCE"]),
        exchange=st.sampled_from(["NFO", "NSE"]),
        ttl=st.integers(min_value=10, max_value=60)
    )
    @hyp_settings(max_examples=20, deadline=None)
    @pytest.mark.asyncio
    async def test_option_chain_cache_ttl(self, underlying, exchange, ttl):
        """
        Property: Option chain cache should use configured TTL.
        """
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
             patch.object(option_chain_cache, 'set', new_callable=AsyncMock) as mock_set, \
             patch('app.services.option.settings') as mock_settings:
            
            mock_get.return_value = None  # Cache miss
            mock_settings.OPTION_CHAIN_CACHE_TTL = ttl
            
            service = OptionService(mock_broker)
            await service.get_option_chain(underlying, exchange)
            
            # Verify cache set was called with TTL
            mock_set.assert_called_once()
            call_kwargs = mock_set.call_args
            assert call_kwargs[1].get('ttl') == ttl


class TestDatabaseIntegrity:
    """Additional database integrity tests"""
    
    @given(
        symbol=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))),
        exchange=st.sampled_from(["NSE", "BSE", "NFO", "BFO"]),
        interval=st.sampled_from(["1m", "5m", "15m", "1h", "1d"])
    )
    @hyp_settings(max_examples=30, deadline=None)
    @pytest.mark.asyncio
    async def test_store_preserves_data_integrity(self, symbol, exchange, interval):
        """
        Property: Stored candles should preserve all data fields.
        """
        candle = OHLCCandle(
            timestamp=int(datetime(2024, 6, 15, 10, 30).timestamp()),
            open=100.50,
            high=101.25,
            low=99.75,
            close=100.80,
            volume=50000
        )
        
        # Track what gets stored
        stored_data = {}
        
        def capture_add(obj):
            stored_data['symbol'] = obj.symbol
            stored_data['exchange'] = obj.exchange
            stored_data['interval'] = obj.interval
            stored_data['open'] = obj.open
            stored_data['high'] = obj.high
            stored_data['low'] = obj.low
            stored_data['close'] = obj.close
            stored_data['volume'] = obj.volume
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.add = MagicMock(side_effect=capture_add)
        mock_db.commit = AsyncMock()
        
        mock_broker = AsyncMock()
        
        service = MarketDataService(mock_broker, mock_db)
        await service._store_candles(symbol, exchange, interval, [candle])
        
        # Verify data integrity
        assert stored_data.get('symbol') == symbol
        assert stored_data.get('exchange') == exchange
        assert stored_data.get('interval') == interval
        assert stored_data.get('open') == candle.open
        assert stored_data.get('high') == candle.high
        assert stored_data.get('low') == candle.low
        assert stored_data.get('close') == candle.close
        assert stored_data.get('volume') == candle.volume
