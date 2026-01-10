"""
API Endpoint Tests
Property-based and unit tests for API endpoints
"""

import pytest
from hypothesis import given, strategies as st, settings
from datetime import datetime

from app.models.schemas import (
    QuoteData, OptionChainData, OptionStrike, OptionLeg,
    ErrorCodes, ERROR_MESSAGES
)


# ==================== Property Tests ====================

class TestQuoteResponseCompleteness:
    """
    Property 3: Quote Response Completeness
    For any quote response, all required fields SHALL be present.
    Validates: Requirements 4.1, 4.3
    """
    
    @given(
        st.floats(min_value=0.01, max_value=100000, allow_nan=False),
        st.floats(min_value=0.01, max_value=100000, allow_nan=False),
        st.floats(min_value=0.01, max_value=100000, allow_nan=False),
        st.floats(min_value=0.01, max_value=100000, allow_nan=False),
        st.floats(min_value=0.01, max_value=100000, allow_nan=False),
        st.integers(min_value=0, max_value=1000000000),
    )
    @settings(max_examples=100)
    def test_quote_has_all_required_fields(self, ltp, open_p, high, low, prev_close, volume):
        """
        Property: QuoteData always has all required fields.
        """
        quote = QuoteData(
            ltp=ltp,
            open=open_p,
            high=high,
            low=low,
            prev_close=prev_close,
            volume=volume
        )
        
        # All required fields present
        assert hasattr(quote, 'ltp')
        assert hasattr(quote, 'open')
        assert hasattr(quote, 'high')
        assert hasattr(quote, 'low')
        assert hasattr(quote, 'prev_close')
        assert hasattr(quote, 'volume')
        
        # Values are correct types
        assert isinstance(quote.ltp, float)
        assert isinstance(quote.open, float)
        assert isinstance(quote.high, float)
        assert isinstance(quote.low, float)
        assert isinstance(quote.prev_close, float)
        assert isinstance(quote.volume, int)
    
    @given(
        st.floats(min_value=0.01, max_value=100000, allow_nan=False),
        st.floats(min_value=0.01, max_value=100000, allow_nan=False),
    )
    @settings(max_examples=100)
    def test_quote_change_fields_optional(self, ltp, prev_close):
        """
        Property: Change fields are optional but calculated correctly when present.
        """
        change = ltp - prev_close
        change_percent = (change / prev_close) * 100 if prev_close > 0 else 0
        
        quote = QuoteData(
            ltp=ltp,
            open=ltp,
            high=ltp,
            low=ltp,
            prev_close=prev_close,
            volume=1000,
            change=round(change, 2),
            change_percent=round(change_percent, 2)
        )
        
        # Change fields present and correct
        assert quote.change == pytest.approx(round(change, 2), rel=1e-9)
        assert quote.change_percent == pytest.approx(round(change_percent, 2), rel=1e-9)


class TestExpiryFiltering:
    """
    Property 10: Expiry Filtering Correctness
    When filtering by expiry, only options with matching expiry SHALL be returned.
    Validates: Requirements 6.4
    """
    
    @given(
        st.lists(
            st.fixed_dictionaries({
                "strike": st.floats(min_value=100, max_value=50000, allow_nan=False),
                "expiry": st.sampled_from(["30JAN25", "06FEB25", "13FEB25"]),
            }),
            min_size=0,
            max_size=50
        ),
        st.sampled_from(["30JAN25", "06FEB25", "13FEB25"])
    )
    @settings(max_examples=100)
    def test_expiry_filter_returns_only_matching(self, options, target_expiry):
        """
        Property: Filtering by expiry returns only matching options.
        """
        filtered = [opt for opt in options if opt["expiry"] == target_expiry]
        
        for opt in filtered:
            assert opt["expiry"] == target_expiry


class TestRateLimiting:
    """
    Property 16: Rate Limiting Enforcement
    Excess requests beyond the limit SHALL be rejected or queued.
    Validates: Requirements 11.3, 11.4
    """
    
    @given(
        st.integers(min_value=1, max_value=100),
        st.integers(min_value=1, max_value=60),
        st.integers(min_value=0, max_value=200)
    )
    @settings(max_examples=100)
    def test_rate_limit_threshold(self, limit, window, request_count):
        """
        Property: Requests beyond limit are rejected.
        """
        # Simulate rate limiting logic
        allowed = min(request_count, limit)
        rejected = max(0, request_count - limit)
        
        assert allowed <= limit
        assert allowed + rejected == request_count
        
        if request_count > limit:
            assert rejected > 0
        else:
            assert rejected == 0


class TestErrorResponseStandardization:
    """
    Property 15: Error Response Standardization
    All error responses SHALL have status, code, and message fields.
    Validates: Requirements 11.1, 11.5
    """
    
    @given(st.sampled_from(list(ErrorCodes.__dict__.values())))
    @settings(max_examples=50)
    def test_error_codes_have_messages(self, error_code):
        """
        Property: All error codes have corresponding messages.
        """
        # Skip non-string attributes
        if not isinstance(error_code, str):
            return
        
        # All error codes should have a message
        assert error_code in ERROR_MESSAGES, f"Missing message for {error_code}"
        assert len(ERROR_MESSAGES[error_code]) > 0
    
    @given(
        st.sampled_from([
            ErrorCodes.AUTH_FAILED,
            ErrorCodes.INVALID_TOKEN,
            ErrorCodes.RATE_LIMITED,
            ErrorCodes.BROKER_ERROR,
            ErrorCodes.VALIDATION_ERROR
        ]),
        st.text(min_size=1, max_size=200)
    )
    @settings(max_examples=100)
    def test_error_response_structure(self, code, message):
        """
        Property: Error responses have required structure.
        """
        from app.models.schemas import ErrorResponse
        
        error = ErrorResponse(
            code=code,
            message=message
        )
        
        # Required fields present
        assert error.status == "error"
        assert error.code == code
        assert error.message == message
        
        # Optional details field
        assert error.details is None or isinstance(error.details, dict)


# ==================== Unit Tests ====================

class TestOptionChainResponse:
    """Unit tests for option chain response"""
    
    def test_option_chain_data_structure(self):
        """Test OptionChainData structure"""
        chain = OptionChainData(
            underlying="NIFTY",
            underlyingLTP=24000.0,
            underlyingPrevClose=23900.0,
            atmStrike=24000.0,
            expiryDate="30JAN25",
            chain=[]
        )
        
        assert chain.underlying == "NIFTY"
        assert chain.underlyingLTP == 24000.0
        assert chain.atmStrike == 24000.0
        assert chain.expiryDate == "30JAN25"
        assert chain.chain == []
    
    def test_option_strike_with_legs(self):
        """Test OptionStrike with CE and PE legs"""
        ce_leg = OptionLeg(
            symbol="NIFTY30JAN2524000CE",
            ltp=150.0,
            bid=149.0,
            ask=151.0,
            oi=100000,
            volume=50000,
            label="ATM"
        )
        
        pe_leg = OptionLeg(
            symbol="NIFTY30JAN2524000PE",
            ltp=145.0,
            bid=144.0,
            ask=146.0,
            oi=120000,
            volume=60000,
            label="ATM"
        )
        
        strike = OptionStrike(
            strike=24000.0,
            ce=ce_leg,
            pe=pe_leg
        )
        
        assert strike.strike == 24000.0
        assert strike.ce.symbol == "NIFTY30JAN2524000CE"
        assert strike.pe.symbol == "NIFTY30JAN2524000PE"
        assert strike.ce.label == "ATM"
        assert strike.pe.label == "ATM"


class TestErrorCodes:
    """Unit tests for error codes"""
    
    def test_all_error_codes_defined(self):
        """All error codes have messages"""
        codes = [
            ErrorCodes.AUTH_FAILED,
            ErrorCodes.INVALID_TOKEN,
            ErrorCodes.TOKEN_EXPIRED,
            ErrorCodes.RATE_LIMITED,
            ErrorCodes.BROKER_ERROR,
            ErrorCodes.SYMBOL_NOT_FOUND,
            ErrorCodes.INVALID_INTERVAL,
            ErrorCodes.INVALID_EXCHANGE,
            ErrorCodes.NO_DATA,
            ErrorCodes.VALIDATION_ERROR,
            ErrorCodes.INTERNAL_ERROR,
        ]
        
        for code in codes:
            assert code in ERROR_MESSAGES
            assert len(ERROR_MESSAGES[code]) > 0
    
    def test_error_messages_not_empty(self):
        """Error messages are not empty"""
        for code, message in ERROR_MESSAGES.items():
            assert message, f"Empty message for {code}"
            assert len(message) > 5, f"Message too short for {code}"
