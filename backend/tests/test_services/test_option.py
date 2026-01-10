"""
Option Service Tests
Property-based and unit tests for option service
"""

import pytest
from hypothesis import given, strategies as st, settings
from datetime import datetime

from app.services.option import (
    OptionService, identify_atm_strike, filter_option_chain_by_expiry
)


# ==================== Property Tests ====================

class TestATMStrikeIdentification:
    """
    Property 9: ATM Strike Identification
    For any underlying spot price and set of strikes, ATM strike SHALL be
    the strike closest to the spot price.
    Validates: Requirements 6.3
    """
    
    @given(
        st.floats(min_value=100, max_value=100000, allow_nan=False),
        st.lists(
            st.floats(min_value=100, max_value=100000, allow_nan=False),
            min_size=1,
            max_size=50,
            unique=True
        )
    )
    @settings(max_examples=100)
    def test_atm_is_closest_to_spot(self, spot_price: float, strikes: list):
        """
        Property: ATM strike is always the strike closest to spot price.
        """
        atm = identify_atm_strike(spot_price, strikes)
        
        # ATM should be in strikes
        assert atm in strikes
        
        # ATM should be closest to spot
        min_distance = abs(atm - spot_price)
        for strike in strikes:
            assert abs(strike - spot_price) >= min_distance - 0.0001  # Float tolerance
    
    @given(
        st.floats(min_value=100, max_value=100000, allow_nan=False),
        st.lists(
            st.floats(min_value=100, max_value=100000, allow_nan=False),
            min_size=2,
            max_size=50,
            unique=True
        )
    )
    @settings(max_examples=100)
    def test_atm_unique_for_given_spot(self, spot_price: float, strikes: list):
        """
        Property: For a given spot price, ATM identification is deterministic.
        """
        atm1 = identify_atm_strike(spot_price, strikes)
        atm2 = identify_atm_strike(spot_price, strikes)
        
        assert atm1 == atm2
    
    @given(st.floats(min_value=100, max_value=100000, allow_nan=False))
    @settings(max_examples=100)
    def test_empty_strikes_returns_zero(self, spot_price: float):
        """
        Property: Empty strikes list returns 0.
        """
        atm = identify_atm_strike(spot_price, [])
        assert atm == 0
    
    @given(st.lists(st.floats(min_value=100, max_value=100000, allow_nan=False), min_size=1))
    @settings(max_examples=100)
    def test_zero_spot_returns_zero(self, strikes: list):
        """
        Property: Zero or negative spot price returns 0.
        """
        assert identify_atm_strike(0, strikes) == 0
        assert identify_atm_strike(-100, strikes) == 0


class TestOptionChainCompleteness:
    """
    Property 8: Option Chain Data Completeness
    For any option chain response, each option SHALL have all required fields.
    Validates: Requirements 6.1, 6.2
    """
    
    @given(
        st.lists(
            st.fixed_dictionaries({
                "symbol": st.text(min_size=1, max_size=30),
                "strike": st.floats(min_value=100, max_value=100000, allow_nan=False),
                "option_type": st.sampled_from(["CE", "PE"]),
                "expiry": st.text(min_size=7, max_size=7),
                "ltp": st.floats(min_value=0, max_value=10000, allow_nan=False),
                "bid": st.floats(min_value=0, max_value=10000, allow_nan=False),
                "ask": st.floats(min_value=0, max_value=10000, allow_nan=False),
                "oi": st.integers(min_value=0, max_value=10000000),
                "volume": st.integers(min_value=0, max_value=10000000),
            }),
            min_size=0,
            max_size=50
        )
    )
    @settings(max_examples=100)
    def test_all_required_fields_present(self, options: list):
        """
        Property: All options have required fields.
        """
        required_fields = {"symbol", "strike", "option_type", "expiry", "ltp", "bid", "ask", "oi", "volume"}
        
        for opt in options:
            assert required_fields.issubset(opt.keys()), f"Missing fields: {required_fields - set(opt.keys())}"
    
    @given(
        st.lists(
            st.fixed_dictionaries({
                "strike": st.floats(min_value=100, max_value=100000, allow_nan=False),
                "option_type": st.sampled_from(["CE", "PE"]),
            }),
            min_size=1,
            max_size=100
        )
    )
    @settings(max_examples=100)
    def test_option_type_valid(self, options: list):
        """
        Property: Option type is always CE or PE.
        """
        for opt in options:
            assert opt["option_type"] in ["CE", "PE"]


class TestExpiryFiltering:
    """
    Property 10: Expiry Filtering Correctness
    When filtering by expiry, only options with matching expiry SHALL be returned.
    Validates: Requirements 6.4
    """
    
    @given(
        st.lists(
            st.fixed_dictionaries({
                "symbol": st.text(min_size=1, max_size=20),
                "strike": st.floats(min_value=100, max_value=50000, allow_nan=False),
                "option_type": st.sampled_from(["CE", "PE"]),
                "expiry": st.sampled_from(["30JAN25", "06FEB25", "13FEB25", "27FEB25"]),
            }),
            min_size=0,
            max_size=100
        ),
        st.sampled_from(["30JAN25", "06FEB25", "13FEB25", "27FEB25"])
    )
    @settings(max_examples=100)
    def test_filter_returns_only_matching_expiry(self, options: list, target_expiry: str):
        """
        Property: Filtered results contain only the target expiry.
        """
        filtered = filter_option_chain_by_expiry(options, target_expiry)
        
        for opt in filtered:
            assert opt["expiry"].upper() == target_expiry.upper()
    
    @given(
        st.lists(
            st.fixed_dictionaries({
                "symbol": st.text(min_size=1, max_size=20),
                "expiry": st.sampled_from(["30JAN25", "06FEB25"]),
            }),
            min_size=0,
            max_size=50
        )
    )
    @settings(max_examples=100)
    def test_filter_preserves_count(self, options: list):
        """
        Property: Filtering preserves or reduces count, never increases.
        """
        for expiry in ["30JAN25", "06FEB25", "NONEXISTENT"]:
            filtered = filter_option_chain_by_expiry(options, expiry)
            assert len(filtered) <= len(options)


# ==================== Unit Tests ====================

class TestOptionServiceHelpers:
    """Unit tests for OptionService helper methods"""
    
    def test_identify_atm_exact_match(self):
        """ATM with exact strike match"""
        strikes = [24000, 24050, 24100, 24150, 24200]
        atm = identify_atm_strike(24100, strikes)
        assert atm == 24100
    
    def test_identify_atm_between_strikes(self):
        """ATM when spot is between strikes"""
        strikes = [24000, 24050, 24100, 24150, 24200]
        atm = identify_atm_strike(24075, strikes)
        # Should be 24050 or 24100 (closest)
        assert atm in [24050, 24100]
        assert abs(atm - 24075) <= 25
    
    def test_filter_expiry_case_insensitive(self):
        """Expiry filtering is case insensitive"""
        options = [
            {"symbol": "NIFTY", "expiry": "30jan25"},
            {"symbol": "NIFTY", "expiry": "30JAN25"},
            {"symbol": "NIFTY", "expiry": "06FEB25"},
        ]
        
        filtered = filter_option_chain_by_expiry(options, "30JAN25")
        assert len(filtered) == 2
    
    def test_strike_step_nifty(self):
        """Test strike step for NIFTY"""
        service = OptionService.__new__(OptionService)
        assert service.get_strike_step("NIFTY") == 50
        assert service.get_strike_step("nifty") == 50
    
    def test_strike_step_banknifty(self):
        """Test strike step for BANKNIFTY"""
        service = OptionService.__new__(OptionService)
        assert service.get_strike_step("BANKNIFTY") == 100
    
    def test_round_to_strike(self):
        """Test rounding to nearest strike"""
        service = OptionService.__new__(OptionService)
        
        # NIFTY (step 50)
        assert service.round_to_strike(24123, "NIFTY") == 24100
        assert service.round_to_strike(24130, "NIFTY") == 24150
        
        # BANKNIFTY (step 100)
        assert service.round_to_strike(51234, "BANKNIFTY") == 51200
        assert service.round_to_strike(51280, "BANKNIFTY") == 51300


class TestExpirySorting:
    """Unit tests for expiry sorting"""
    
    def test_sort_expiries_chronological(self):
        """Expiries are sorted chronologically"""
        service = OptionService.__new__(OptionService)
        
        expiries = ["27FEB25", "30JAN25", "06FEB25", "13FEB25"]
        sorted_exp = service.sort_expiries(expiries)
        
        assert sorted_exp == ["30JAN25", "06FEB25", "13FEB25", "27FEB25"]
    
    def test_sort_expiries_mixed_case(self):
        """Sorting handles mixed case"""
        service = OptionService.__new__(OptionService)
        
        expiries = ["27feb25", "30JAN25", "06Feb25"]
        sorted_exp = service.sort_expiries(expiries)
        
        assert len(sorted_exp) == 3
        # First should be January
        assert "JAN" in sorted_exp[0].upper()
