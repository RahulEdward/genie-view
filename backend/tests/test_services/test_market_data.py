"""
Market Data Service Tests
Property-based and unit tests for market data service
"""

import pytest
from hypothesis import given, strategies as st, settings
from datetime import datetime, timedelta

from app.services.market_data import (
    calculate_change, convert_timestamp_to_ist, convert_timestamp_from_ist,
    IST_OFFSET_SECONDS, MarketDataService
)
from app.brokers.base import OHLCCandle


# ==================== Property Tests ====================

class TestCacheFirstFetching:
    """
    Property 5: Cache-First Data Fetching
    For any historical data request, the system SHALL first check cache,
    then database, and only fetch missing ranges from broker.
    Validates: Requirements 3.4
    """
    
    @given(
        st.lists(
            st.integers(min_value=1704067200, max_value=1735689600),  # 2024-2025 timestamps
            min_size=0,
            max_size=50,
            unique=True
        ).map(sorted),
        st.integers(min_value=1704067200, max_value=1735689600),
        st.integers(min_value=1704067200, max_value=1735689600)
    )
    @settings(max_examples=100)
    def test_missing_ranges_identified_correctly(self, existing_timestamps, from_ts, to_ts):
        """
        Property: For any set of existing candles and date range,
        _find_missing_ranges correctly identifies gaps.
        """
        # Ensure from < to
        if from_ts >= to_ts:
            from_ts, to_ts = to_ts, from_ts + 86400
        
        # Create candles from timestamps
        candles = [
            OHLCCandle(timestamp=ts, open=100, high=101, low=99, close=100, volume=1000)
            for ts in existing_timestamps
            if from_ts <= ts <= to_ts
        ]
        
        from_dt = datetime.fromtimestamp(from_ts)
        to_dt = datetime.fromtimestamp(to_ts)
        
        # Create service with mock dependencies
        service = MarketDataService.__new__(MarketDataService)
        
        missing = service._find_missing_ranges(candles, from_dt, to_dt, "1d")
        
        # If no candles, entire range should be missing
        if not candles:
            assert len(missing) == 1
            assert missing[0][0] == from_dt
            assert missing[0][1] == to_dt
        else:
            # Missing ranges should not overlap with existing data
            for start, end in missing:
                for candle in candles:
                    candle_dt = datetime.fromtimestamp(candle.timestamp)
                    # Missing range should not contain existing candle timestamps
                    # (with some tolerance for interval boundaries)
                    assert not (start <= candle_dt <= end) or \
                           abs((candle_dt - start).total_seconds()) < 86400 or \
                           abs((end - candle_dt).total_seconds()) < 86400
    
    @given(
        st.integers(min_value=1704067200, max_value=1735689600),
        st.integers(min_value=1, max_value=30)
    )
    @settings(max_examples=100)
    def test_no_missing_ranges_when_data_complete(self, start_ts, num_days):
        """
        Property: When all data exists in cache, no missing ranges are returned.
        """
        # Create complete daily candles
        candles = [
            OHLCCandle(
                timestamp=start_ts + (i * 86400),
                open=100, high=101, low=99, close=100, volume=1000
            )
            for i in range(num_days)
        ]
        
        from_dt = datetime.fromtimestamp(start_ts)
        to_dt = datetime.fromtimestamp(start_ts + (num_days - 1) * 86400)
        
        service = MarketDataService.__new__(MarketDataService)
        missing = service._find_missing_ranges(candles, from_dt, to_dt, "1d")
        
        # No missing ranges when data is complete
        assert len(missing) == 0


class TestTimestampConversion:
    """
    Property 6: Timestamp Timezone Consistency
    For any timestamp, converting to IST and back SHALL return the original value.
    Validates: Requirements 3.6
    """
    
    @given(st.integers(min_value=0, max_value=2000000000))
    @settings(max_examples=100)
    def test_timestamp_roundtrip(self, timestamp: int):
        """
        Property: Converting timestamp to IST and back returns original value.
        """
        ist_timestamp = convert_timestamp_to_ist(timestamp)
        original = convert_timestamp_from_ist(ist_timestamp)
        
        assert original == timestamp
    
    @given(st.integers(min_value=0, max_value=2000000000))
    @settings(max_examples=100)
    def test_ist_offset_correct(self, timestamp: int):
        """
        Property: IST offset is exactly 5 hours 30 minutes (19800 seconds).
        """
        ist_timestamp = convert_timestamp_to_ist(timestamp)
        
        assert ist_timestamp - timestamp == IST_OFFSET_SECONDS
        assert IST_OFFSET_SECONDS == 19800  # 5.5 hours
    
    @given(st.integers(min_value=0, max_value=2000000000))
    @settings(max_examples=100)
    def test_ist_always_greater(self, timestamp: int):
        """
        Property: IST timestamp is always greater than UTC timestamp.
        """
        ist_timestamp = convert_timestamp_to_ist(timestamp)
        
        assert ist_timestamp > timestamp


class TestPriceChangeCalculation:
    """
    Property 2: Price Change Calculation Correctness
    For any LTP and previous close, change calculation SHALL be mathematically correct.
    Validates: Requirements 4.2
    """
    
    @given(
        st.floats(min_value=0.01, max_value=100000, allow_nan=False),
        st.floats(min_value=0.01, max_value=100000, allow_nan=False)
    )
    @settings(max_examples=100)
    def test_change_calculation_correct(self, ltp: float, prev_close: float):
        """
        Property: Change = LTP - prev_close, change_percent = (change/prev_close) * 100
        """
        change, change_percent = calculate_change(ltp, prev_close)
        
        expected_change = ltp - prev_close
        expected_percent = (expected_change / prev_close) * 100
        
        assert change == pytest.approx(round(expected_change, 2), rel=1e-9)
        assert change_percent == pytest.approx(round(expected_percent, 2), rel=1e-9)
    
    @given(st.floats(min_value=0.01, max_value=100000, allow_nan=False))
    @settings(max_examples=100)
    def test_zero_prev_close_returns_zero(self, ltp: float):
        """
        Property: When prev_close is 0 or negative, returns (0, 0).
        """
        change, change_percent = calculate_change(ltp, 0)
        assert change == 0.0
        assert change_percent == 0.0
        
        change, change_percent = calculate_change(ltp, -1)
        assert change == 0.0
        assert change_percent == 0.0
    
    @given(st.floats(min_value=0.01, max_value=100000, allow_nan=False))
    @settings(max_examples=100)
    def test_no_change_when_equal(self, price: float):
        """
        Property: When LTP equals prev_close, change is 0.
        """
        change, change_percent = calculate_change(price, price)
        
        assert change == 0.0
        assert change_percent == 0.0
    
    @given(
        st.floats(min_value=0.01, max_value=100000, allow_nan=False),
        st.floats(min_value=0.01, max_value=100000, allow_nan=False)
    )
    @settings(max_examples=100)
    def test_change_sign_correct(self, ltp: float, prev_close: float):
        """
        Property: Change is positive when LTP > prev_close, negative otherwise.
        """
        change, change_percent = calculate_change(ltp, prev_close)
        
        if ltp > prev_close:
            assert change > 0
            assert change_percent > 0
        elif ltp < prev_close:
            assert change < 0
            assert change_percent < 0
        else:
            assert change == 0
            assert change_percent == 0


class TestDeduplication:
    """Test candle deduplication"""
    
    @given(
        st.lists(
            st.integers(min_value=1704067200, max_value=1735689600),
            min_size=1,
            max_size=100
        )
    )
    @settings(max_examples=100)
    def test_deduplication_keeps_unique_timestamps(self, timestamps):
        """
        Property: After deduplication, all timestamps are unique.
        """
        candles = [
            OHLCCandle(timestamp=ts, open=100, high=101, low=99, close=100, volume=1000)
            for ts in timestamps
        ]
        
        service = MarketDataService.__new__(MarketDataService)
        result = service._deduplicate_candles(candles)
        
        result_timestamps = [c.timestamp for c in result]
        assert len(result_timestamps) == len(set(result_timestamps))
    
    @given(
        st.lists(
            st.integers(min_value=1704067200, max_value=1735689600),
            min_size=1,
            max_size=100,
            unique=True
        )
    )
    @settings(max_examples=100)
    def test_deduplication_preserves_unique_candles(self, timestamps):
        """
        Property: Unique candles are preserved after deduplication.
        """
        candles = [
            OHLCCandle(timestamp=ts, open=100, high=101, low=99, close=100, volume=1000)
            for ts in timestamps
        ]
        
        service = MarketDataService.__new__(MarketDataService)
        result = service._deduplicate_candles(candles)
        
        assert len(result) == len(candles)


# ==================== Unit Tests ====================

class TestIntervalMinutes:
    """Unit tests for interval to minutes conversion"""
    
    def test_minute_intervals(self):
        """Test minute interval conversions"""
        service = MarketDataService.__new__(MarketDataService)
        
        assert service._get_interval_minutes("1m") == 1
        assert service._get_interval_minutes("ONE_MINUTE") == 1
        assert service._get_interval_minutes("5m") == 5
        assert service._get_interval_minutes("FIVE_MINUTE") == 5
        assert service._get_interval_minutes("15m") == 15
        assert service._get_interval_minutes("30m") == 30
    
    def test_hour_intervals(self):
        """Test hour interval conversions"""
        service = MarketDataService.__new__(MarketDataService)
        
        assert service._get_interval_minutes("1h") == 60
        assert service._get_interval_minutes("ONE_HOUR") == 60
        assert service._get_interval_minutes("4h") == 240
    
    def test_day_intervals(self):
        """Test day interval conversions"""
        service = MarketDataService.__new__(MarketDataService)
        
        assert service._get_interval_minutes("1d") == 1440
        assert service._get_interval_minutes("ONE_DAY") == 1440
        assert service._get_interval_minutes("1w") == 10080
    
    def test_unknown_interval_defaults_to_1(self):
        """Unknown intervals default to 1 minute"""
        service = MarketDataService.__new__(MarketDataService)
        
        assert service._get_interval_minutes("unknown") == 1
