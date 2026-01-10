"""
Angel One Adapter Tests
Property-based and unit tests for Angel One adapter
"""

import pytest
from hypothesis import given, strategies as st, settings
from datetime import datetime

from app.brokers.angelone.transformers import (
    transform_candle_data, transform_quote_data,
    transform_symbol_info, parse_angel_error, normalize_expiry
)
from app.brokers.angelone.endpoints import ERROR_CODE_MAP
from app.brokers.base import OHLCCandle, Quote, SymbolInfo


# ==================== Property Tests ====================

class TestAuthenticationErrorMapping:
    """
    Property 19: Authentication Error Mapping
    For any failed authentication attempt, the error response SHALL contain
    the original broker error code and a mapped user-friendly message.
    Validates: Requirements 2.4
    """
    
    @given(st.sampled_from(list(ERROR_CODE_MAP.keys())))
    @settings(max_examples=100)
    def test_known_error_codes_map_correctly(self, error_code: str):
        """
        Property: For any known Angel One error code, parse_angel_error
        returns a valid internal code and non-empty message.
        """
        response = {
            "errorcode": error_code,
            "message": f"Test error for {error_code}"
        }
        
        internal_code, message = parse_angel_error(response)
        
        # Internal code should be from our defined set
        valid_codes = {"AUTH_FAILED", "INVALID_TOKEN", "RATE_LIMITED", 
                       "BROKER_ERROR", "SYMBOL_NOT_FOUND", "INVALID_EXCHANGE", "NO_DATA"}
        assert internal_code in valid_codes, f"Unknown internal code: {internal_code}"
        
        # Message should not be empty
        assert message, "Error message should not be empty"
        assert len(message) > 0
    
    @given(st.text(min_size=1, max_size=20))
    @settings(max_examples=100)
    def test_unknown_error_codes_return_broker_error(self, error_code: str):
        """
        Property: For any unknown error code, parse_angel_error returns
        BROKER_ERROR with the original message.
        """
        # Skip if it happens to be a known code
        if error_code in ERROR_CODE_MAP:
            return
        
        original_message = f"Unknown error: {error_code}"
        response = {
            "errorcode": error_code,
            "message": original_message
        }
        
        internal_code, message = parse_angel_error(response)
        
        # Unknown codes should map to BROKER_ERROR
        assert internal_code == "BROKER_ERROR"
        # Original message should be preserved
        assert message == original_message
    
    @given(st.text(min_size=0, max_size=200))
    @settings(max_examples=100)
    def test_error_message_always_present(self, custom_message: str):
        """
        Property: parse_angel_error always returns a non-None message.
        """
        response = {
            "errorcode": "AB1000",
            "message": custom_message if custom_message else None
        }
        
        internal_code, message = parse_angel_error(response)
        
        # Message should never be None
        assert message is not None
        # If custom message was empty/None, should use default
        if not custom_message:
            assert len(message) > 0


class TestOHLCTransformation:
    """
    Property 1: OHLC Data Transformation Preserves Integrity
    For any broker response containing OHLC candle data, transforming it
    to standardized format SHALL preserve all numeric values.
    Validates: Requirements 3.5, 10.2
    """
    
    @given(
        st.lists(
            st.tuples(
                st.integers(min_value=0, max_value=2000000000),  # timestamp
                st.floats(min_value=0.01, max_value=100000, allow_nan=False),  # open
                st.floats(min_value=0.01, max_value=100000, allow_nan=False),  # high
                st.floats(min_value=0.01, max_value=100000, allow_nan=False),  # low
                st.floats(min_value=0.01, max_value=100000, allow_nan=False),  # close
                st.integers(min_value=0, max_value=1000000000)  # volume
            ),
            min_size=0,
            max_size=100
        )
    )
    @settings(max_examples=100)
    def test_candle_data_preserves_values(self, raw_data):
        """
        Property: For any valid OHLC data, transformation preserves
        all numeric values without loss.
        """
        # Convert tuples to lists (Angel One format)
        data = [list(row) for row in raw_data]
        
        candles = transform_candle_data(data)
        
        # Same number of candles
        assert len(candles) == len(data)
        
        # Each candle preserves values
        for i, candle in enumerate(candles):
            assert candle.timestamp == data[i][0]
            assert candle.open == pytest.approx(data[i][1], rel=1e-9)
            assert candle.high == pytest.approx(data[i][2], rel=1e-9)
            assert candle.low == pytest.approx(data[i][3], rel=1e-9)
            assert candle.close == pytest.approx(data[i][4], rel=1e-9)
            assert candle.volume == data[i][5]
    
    @given(
        st.floats(min_value=0.01, max_value=100000, allow_nan=False),
        st.floats(min_value=0.01, max_value=100000, allow_nan=False),
        st.floats(min_value=0.01, max_value=100000, allow_nan=False),
        st.floats(min_value=0.01, max_value=100000, allow_nan=False),
    )
    @settings(max_examples=100)
    def test_candle_ohlc_types_correct(self, open_p, high_p, low_p, close_p):
        """
        Property: Transformed candles have correct types for all fields.
        """
        data = [[1704067200, open_p, high_p, low_p, close_p, 1000]]
        candles = transform_candle_data(data)
        
        assert len(candles) == 1
        candle = candles[0]
        
        assert isinstance(candle.timestamp, int)
        assert isinstance(candle.open, float)
        assert isinstance(candle.high, float)
        assert isinstance(candle.low, float)
        assert isinstance(candle.close, float)
        assert isinstance(candle.volume, int)


class TestExpiryNormalization:
    """Test expiry date normalization"""
    
    @given(st.dates(min_value=datetime(2020, 1, 1).date(), max_value=datetime(2030, 12, 31).date()))
    @settings(max_examples=100)
    def test_iso_format_normalizes_correctly(self, date):
        """
        Property: ISO format dates normalize to DDMMMYY format.
        """
        iso_str = date.strftime("%Y-%m-%d")
        result = normalize_expiry(iso_str)
        
        # Result should be 7 characters
        assert len(result) == 7
        # First 2 chars should be day
        assert result[:2].isdigit()
        # Middle 3 chars should be month abbreviation
        assert result[2:5].isalpha()
        # Last 2 chars should be year
        assert result[5:].isdigit()
    
    def test_already_normalized_unchanged(self):
        """Already normalized expiry should remain unchanged"""
        expiry = "30JAN25"
        assert normalize_expiry(expiry) == "30JAN25"
        
        expiry_lower = "30jan25"
        assert normalize_expiry(expiry_lower) == "30JAN25"


# ==================== Unit Tests ====================

class TestTransformQuoteData:
    """Unit tests for quote transformation"""
    
    def test_transform_full_quote(self):
        """Test transforming complete quote data"""
        data = {
            "fetched": [{
                "ltp": 105.50,
                "open": 103.00,
                "high": 107.00,
                "low": 102.50,
                "close": 104.00,
                "tradeVolume": 50000,
                "depth": {
                    "buy": [{"price": 105.45, "quantity": 100}],
                    "sell": [{"price": 105.55, "quantity": 150}]
                }
            }]
        }
        
        quote = transform_quote_data(data, "RELIANCE", "NSE")
        
        assert quote.symbol == "RELIANCE"
        assert quote.exchange == "NSE"
        assert quote.ltp == 105.50
        assert quote.open == 103.00
        assert quote.high == 107.00
        assert quote.low == 102.50
        assert quote.prev_close == 104.00
        assert quote.volume == 50000
        assert quote.bid == 105.45
        assert quote.ask == 105.55
    
    def test_transform_empty_quote(self):
        """Test transforming empty quote data"""
        data = {"fetched": []}
        
        quote = transform_quote_data(data, "RELIANCE", "NSE")
        
        assert quote.symbol == "RELIANCE"
        assert quote.ltp == 0


class TestTransformSymbolInfo:
    """Unit tests for symbol info transformation"""
    
    def test_transform_equity_symbol(self):
        """Test transforming equity symbol"""
        data = {
            "tradingsymbol": "RELIANCE-EQ",
            "symboltoken": "2885",
            "name": "RELIANCE INDUSTRIES",
            "exchange": "NSE",
            "instrumenttype": "EQ",
            "lotsize": 1,
            "tick_size": 0.05
        }
        
        info = transform_symbol_info(data)
        
        assert info.symbol == "RELIANCE-EQ"
        assert info.token == "2885"
        assert info.name == "RELIANCE INDUSTRIES"
        assert info.exchange == "NSE"
        assert info.lot_size == 1
    
    def test_transform_option_symbol(self):
        """Test transforming option symbol"""
        data = {
            "tradingsymbol": "NIFTY30JAN2524000CE",
            "symboltoken": "12345",
            "exchange": "NFO",
            "instrumenttype": "OPTIDX",
            "lotsize": 50,
            "expiry": "2025-01-30",
            "strike": 24000,
            "optiontype": "CE"
        }
        
        info = transform_symbol_info(data)
        
        assert info.symbol == "NIFTY30JAN2524000CE"
        assert info.exchange == "NFO"
        assert info.lot_size == 50
        assert info.strike == 24000
        assert info.option_type == "CE"
        assert info.expiry == "30JAN25"
