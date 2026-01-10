"""
Greeks Calculation Tests
Property-based and unit tests for Black-Scholes Greeks
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
import math

from app.utils.greeks import (
    calculate_greeks, calculate_delta, calculate_gamma, calculate_theta,
    calculate_vega, calculate_iv, black_scholes_price, norm_cdf, norm_pdf
)
from app.brokers.base import Greeks


# ==================== Property Tests ====================

class TestGreeksValidity:
    """
    Property 11: Greeks Calculation Validity
    For any valid option parameters, calculated Greeks SHALL be within valid ranges.
    Validates: Requirements 7.1, 7.2, 7.5
    """
    
    @given(
        st.floats(min_value=100, max_value=100000, allow_nan=False),  # spot
        st.floats(min_value=100, max_value=100000, allow_nan=False),  # strike
        st.floats(min_value=1, max_value=365, allow_nan=False),       # expiry_days
        st.floats(min_value=0.01, max_value=0.20, allow_nan=False),   # rate
        st.sampled_from(["CE", "PE"]),                                 # option_type
        st.floats(min_value=0.05, max_value=2.0, allow_nan=False),    # volatility
    )
    @settings(max_examples=100)
    def test_delta_in_valid_range(self, spot, strike, expiry_days, rate, option_type, volatility):
        """
        Property: Delta is always between -1 and 1.
        Call delta: 0 to 1, Put delta: -1 to 0
        """
        greeks = calculate_greeks(
            spot=spot,
            strike=strike,
            expiry_days=expiry_days,
            rate=rate,
            option_type=option_type,
            volatility=volatility
        )
        
        assert -1 <= greeks.delta <= 1, f"Delta {greeks.delta} out of range"
        
        if option_type == "CE":
            assert 0 <= greeks.delta <= 1, f"Call delta {greeks.delta} should be 0-1"
        else:
            assert -1 <= greeks.delta <= 0, f"Put delta {greeks.delta} should be -1 to 0"
    
    @given(
        st.floats(min_value=100, max_value=100000, allow_nan=False),
        st.floats(min_value=100, max_value=100000, allow_nan=False),
        st.floats(min_value=1, max_value=365, allow_nan=False),
        st.floats(min_value=0.01, max_value=0.20, allow_nan=False),
        st.sampled_from(["CE", "PE"]),
        st.floats(min_value=0.05, max_value=2.0, allow_nan=False),
    )
    @settings(max_examples=100)
    def test_gamma_always_positive(self, spot, strike, expiry_days, rate, option_type, volatility):
        """
        Property: Gamma is always non-negative.
        """
        greeks = calculate_greeks(
            spot=spot,
            strike=strike,
            expiry_days=expiry_days,
            rate=rate,
            option_type=option_type,
            volatility=volatility
        )
        
        assert greeks.gamma >= 0, f"Gamma {greeks.gamma} should be non-negative"
    
    @given(
        st.floats(min_value=100, max_value=100000, allow_nan=False),
        st.floats(min_value=100, max_value=100000, allow_nan=False),
        st.floats(min_value=1, max_value=365, allow_nan=False),
        st.floats(min_value=0.01, max_value=0.20, allow_nan=False),
        st.sampled_from(["CE", "PE"]),
        st.floats(min_value=0.05, max_value=2.0, allow_nan=False),
    )
    @settings(max_examples=100)
    def test_vega_always_positive(self, spot, strike, expiry_days, rate, option_type, volatility):
        """
        Property: Vega is always non-negative.
        """
        greeks = calculate_greeks(
            spot=spot,
            strike=strike,
            expiry_days=expiry_days,
            rate=rate,
            option_type=option_type,
            volatility=volatility
        )
        
        assert greeks.vega >= 0, f"Vega {greeks.vega} should be non-negative"
    
    @given(
        st.floats(min_value=100, max_value=100000, allow_nan=False),
        st.floats(min_value=100, max_value=100000, allow_nan=False),
        st.floats(min_value=1, max_value=365, allow_nan=False),
        st.floats(min_value=0.01, max_value=0.20, allow_nan=False),
        st.sampled_from(["CE", "PE"]),
        st.floats(min_value=0.05, max_value=2.0, allow_nan=False),
    )
    @settings(max_examples=100)
    def test_iv_in_valid_range(self, spot, strike, expiry_days, rate, option_type, volatility):
        """
        Property: IV is always non-negative and reasonable (0-500%).
        """
        greeks = calculate_greeks(
            spot=spot,
            strike=strike,
            expiry_days=expiry_days,
            rate=rate,
            option_type=option_type,
            volatility=volatility
        )
        
        assert 0 <= greeks.iv <= 500, f"IV {greeks.iv}% out of reasonable range"


class TestBlackScholesConsistency:
    """Test Black-Scholes model consistency"""
    
    @given(
        st.floats(min_value=100, max_value=50000, allow_nan=False),
        st.floats(min_value=100, max_value=50000, allow_nan=False),
        st.floats(min_value=0.01, max_value=1.0, allow_nan=False),
        st.floats(min_value=0.01, max_value=0.15, allow_nan=False),
        st.floats(min_value=0.1, max_value=1.0, allow_nan=False),
    )
    @settings(max_examples=100)
    def test_put_call_parity(self, spot, strike, time_to_expiry, rate, volatility):
        """
        Property: Put-Call parity holds: C - P = S - K*e^(-rT)
        """
        call_price = black_scholes_price(spot, strike, time_to_expiry, rate, volatility, "CE")
        put_price = black_scholes_price(spot, strike, time_to_expiry, rate, volatility, "PE")
        
        # Put-Call parity
        expected_diff = spot - strike * math.exp(-rate * time_to_expiry)
        actual_diff = call_price - put_price
        
        assert abs(actual_diff - expected_diff) < 0.01, \
            f"Put-Call parity violated: {actual_diff} != {expected_diff}"
    
    @given(
        st.floats(min_value=100, max_value=50000, allow_nan=False),
        st.floats(min_value=0.01, max_value=1.0, allow_nan=False),
        st.floats(min_value=0.01, max_value=0.15, allow_nan=False),
        st.floats(min_value=0.1, max_value=1.0, allow_nan=False),
    )
    @settings(max_examples=100)
    def test_atm_call_delta_near_half(self, spot, time_to_expiry, rate, volatility):
        """
        Property: ATM call delta is approximately 0.5 (slightly higher due to drift).
        """
        delta = calculate_delta(spot, spot, time_to_expiry, rate, volatility, "CE")
        
        # ATM call delta should be around 0.5-0.6
        assert 0.4 <= delta <= 0.7, f"ATM call delta {delta} not near 0.5"
    
    @given(
        st.floats(min_value=100, max_value=50000, allow_nan=False),
        st.floats(min_value=0.01, max_value=1.0, allow_nan=False),
        st.floats(min_value=0.01, max_value=0.15, allow_nan=False),
        st.floats(min_value=0.1, max_value=1.0, allow_nan=False),
    )
    @settings(max_examples=100)
    def test_deep_itm_call_delta_near_one(self, spot, time_to_expiry, rate, volatility):
        """
        Property: Deep ITM call delta approaches 1.
        """
        strike = spot * 0.7  # 30% ITM
        delta = calculate_delta(spot, strike, time_to_expiry, rate, volatility, "CE")
        
        assert delta > 0.9, f"Deep ITM call delta {delta} should be near 1"
    
    @given(
        st.floats(min_value=100, max_value=50000, allow_nan=False),
        st.floats(min_value=0.01, max_value=1.0, allow_nan=False),
        st.floats(min_value=0.01, max_value=0.15, allow_nan=False),
        st.floats(min_value=0.1, max_value=1.0, allow_nan=False),
    )
    @settings(max_examples=100)
    def test_deep_otm_call_delta_near_zero(self, spot, time_to_expiry, rate, volatility):
        """
        Property: Deep OTM call delta approaches 0.
        """
        strike = spot * 1.3  # 30% OTM
        delta = calculate_delta(spot, strike, time_to_expiry, rate, volatility, "CE")
        
        assert delta < 0.1, f"Deep OTM call delta {delta} should be near 0"


class TestIVCalculation:
    """Test IV calculation via Newton-Raphson"""
    
    @given(
        st.floats(min_value=100, max_value=50000, allow_nan=False),
        st.floats(min_value=100, max_value=50000, allow_nan=False),
        st.floats(min_value=0.05, max_value=0.5, allow_nan=False),
        st.floats(min_value=0.01, max_value=0.15, allow_nan=False),
        st.floats(min_value=0.1, max_value=1.0, allow_nan=False),
        st.sampled_from(["CE", "PE"]),
    )
    @settings(max_examples=50)
    def test_iv_roundtrip(self, spot, strike, time_to_expiry, rate, known_iv, option_type):
        """
        Property: Calculating price from IV, then IV from price, returns original IV.
        """
        # Skip extreme cases
        assume(0.5 < spot/strike < 2.0)
        
        # Calculate price from known IV
        price = black_scholes_price(spot, strike, time_to_expiry, rate, known_iv, option_type)
        
        # Skip if price is too small
        assume(price > 0.1)
        
        # Calculate IV from price
        calculated_iv = calculate_iv(price, spot, strike, time_to_expiry, rate, option_type)
        
        # Should be close to original
        assert abs(calculated_iv - known_iv) < 0.02, \
            f"IV roundtrip failed: {known_iv} -> {calculated_iv}"


# ==================== Unit Tests ====================

class TestNormalDistribution:
    """Unit tests for normal distribution functions"""
    
    def test_norm_cdf_at_zero(self):
        """CDF at 0 is 0.5"""
        assert abs(norm_cdf(0) - 0.5) < 0.0001
    
    def test_norm_cdf_symmetry(self):
        """CDF is symmetric: N(x) + N(-x) = 1"""
        for x in [0.5, 1.0, 1.5, 2.0]:
            assert abs(norm_cdf(x) + norm_cdf(-x) - 1.0) < 0.0001
    
    def test_norm_pdf_at_zero(self):
        """PDF at 0 is 1/sqrt(2*pi)"""
        expected = 1 / math.sqrt(2 * math.pi)
        assert abs(norm_pdf(0) - expected) < 0.0001
    
    def test_norm_pdf_symmetry(self):
        """PDF is symmetric: f(x) = f(-x)"""
        for x in [0.5, 1.0, 1.5, 2.0]:
            assert abs(norm_pdf(x) - norm_pdf(-x)) < 0.0001


class TestGreeksEdgeCases:
    """Unit tests for edge cases"""
    
    def test_expired_option_call_itm(self):
        """Expired ITM call has delta 1"""
        delta = calculate_delta(100, 90, 0, 0.07, 0.2, "CE")
        assert delta == 1.0
    
    def test_expired_option_call_otm(self):
        """Expired OTM call has delta 0"""
        delta = calculate_delta(100, 110, 0, 0.07, 0.2, "CE")
        assert delta == 0.0
    
    def test_expired_option_put_itm(self):
        """Expired ITM put has delta -1"""
        delta = calculate_delta(100, 110, 0, 0.07, 0.2, "PE")
        assert delta == -1.0
    
    def test_expired_option_put_otm(self):
        """Expired OTM put has delta 0"""
        delta = calculate_delta(100, 90, 0, 0.07, 0.2, "PE")
        assert delta == 0.0
    
    def test_zero_time_gamma(self):
        """Gamma at expiry is 0"""
        gamma = calculate_gamma(100, 100, 0, 0.07, 0.2)
        assert gamma == 0
    
    def test_zero_time_vega(self):
        """Vega at expiry is 0"""
        vega = calculate_vega(100, 100, 0, 0.07, 0.2)
        assert vega == 0


class TestGreeksCalculation:
    """Unit tests for Greeks calculation"""
    
    def test_calculate_greeks_returns_greeks_object(self):
        """calculate_greeks returns Greeks object"""
        result = calculate_greeks(
            spot=24000,
            strike=24000,
            expiry_days=7,
            rate=0.07,
            option_type="CE",
            volatility=0.15
        )
        
        assert isinstance(result, Greeks)
        assert hasattr(result, 'delta')
        assert hasattr(result, 'gamma')
        assert hasattr(result, 'theta')
        assert hasattr(result, 'vega')
        assert hasattr(result, 'iv')
    
    def test_atm_option_greeks(self):
        """ATM option has reasonable Greeks"""
        result = calculate_greeks(
            spot=24000,
            strike=24000,
            expiry_days=30,
            rate=0.07,
            option_type="CE",
            volatility=0.15
        )
        
        # ATM call delta around 0.5
        assert 0.4 < result.delta < 0.7
        # Gamma positive
        assert result.gamma > 0
        # Theta negative (time decay)
        assert result.theta < 0
        # Vega positive
        assert result.vega > 0
        # IV should be 15%
        assert result.iv == 15.0
