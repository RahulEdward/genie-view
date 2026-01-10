"""
Greeks Calculation Module
Black-Scholes model implementation for option Greeks
"""

import math
from typing import Dict, Optional, Tuple
from dataclasses import dataclass

from app.brokers.base import Greeks


# Constants
DAYS_IN_YEAR = 365
TRADING_DAYS = 252


@dataclass
class GreeksInput:
    """Input parameters for Greeks calculation"""
    spot: float           # Underlying spot price
    strike: float         # Option strike price
    expiry_days: float    # Days to expiry
    rate: float           # Risk-free rate (annual, decimal)
    option_type: str      # "CE" or "PE"
    option_price: float   # Current option price (for IV calculation)
    dividend: float = 0   # Dividend yield (annual, decimal)


def norm_cdf(x: float) -> float:
    """
    Standard normal cumulative distribution function.
    Uses approximation for efficiency.
    """
    # Constants for approximation
    a1 = 0.254829592
    a2 = -0.284496736
    a3 = 1.421413741
    a4 = -1.453152027
    a5 = 1.061405429
    p = 0.3275911
    
    sign = 1 if x >= 0 else -1
    x = abs(x) / math.sqrt(2)
    
    t = 1.0 / (1.0 + p * x)
    y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * math.exp(-x * x)
    
    return 0.5 * (1.0 + sign * y)


def norm_pdf(x: float) -> float:
    """Standard normal probability density function."""
    return math.exp(-0.5 * x * x) / math.sqrt(2 * math.pi)


def calculate_d1_d2(
    spot: float,
    strike: float,
    time_to_expiry: float,
    rate: float,
    volatility: float,
    dividend: float = 0
) -> Tuple[float, float]:
    """
    Calculate d1 and d2 for Black-Scholes formula.
    
    Args:
        spot: Underlying spot price
        strike: Option strike price
        time_to_expiry: Time to expiry in years
        rate: Risk-free rate (annual, decimal)
        volatility: Implied volatility (annual, decimal)
        dividend: Dividend yield (annual, decimal)
    
    Returns:
        Tuple of (d1, d2)
    """
    if time_to_expiry <= 0 or volatility <= 0 or spot <= 0 or strike <= 0:
        return 0, 0
    
    sqrt_t = math.sqrt(time_to_expiry)
    
    d1 = (math.log(spot / strike) + (rate - dividend + 0.5 * volatility ** 2) * time_to_expiry) / (volatility * sqrt_t)
    d2 = d1 - volatility * sqrt_t
    
    return d1, d2


def black_scholes_price(
    spot: float,
    strike: float,
    time_to_expiry: float,
    rate: float,
    volatility: float,
    option_type: str,
    dividend: float = 0
) -> float:
    """
    Calculate option price using Black-Scholes model.
    
    Args:
        spot: Underlying spot price
        strike: Option strike price
        time_to_expiry: Time to expiry in years
        rate: Risk-free rate (annual, decimal)
        volatility: Implied volatility (annual, decimal)
        option_type: "CE" for call, "PE" for put
        dividend: Dividend yield (annual, decimal)
    
    Returns:
        Theoretical option price
    """
    if time_to_expiry <= 0:
        # At expiry, return intrinsic value
        if option_type.upper() == "CE":
            return max(0, spot - strike)
        else:
            return max(0, strike - spot)
    
    d1, d2 = calculate_d1_d2(spot, strike, time_to_expiry, rate, volatility, dividend)
    
    discount = math.exp(-rate * time_to_expiry)
    dividend_discount = math.exp(-dividend * time_to_expiry)
    
    if option_type.upper() == "CE":
        price = spot * dividend_discount * norm_cdf(d1) - strike * discount * norm_cdf(d2)
    else:
        price = strike * discount * norm_cdf(-d2) - spot * dividend_discount * norm_cdf(-d1)
    
    return max(0, price)


def calculate_iv(
    option_price: float,
    spot: float,
    strike: float,
    time_to_expiry: float,
    rate: float,
    option_type: str,
    dividend: float = 0,
    max_iterations: int = 100,
    tolerance: float = 0.0001
) -> float:
    """
    Calculate Implied Volatility using Newton-Raphson method.
    
    Args:
        option_price: Market price of option
        spot: Underlying spot price
        strike: Option strike price
        time_to_expiry: Time to expiry in years
        rate: Risk-free rate (annual, decimal)
        option_type: "CE" for call, "PE" for put
        dividend: Dividend yield (annual, decimal)
        max_iterations: Maximum iterations for convergence
        tolerance: Convergence tolerance
    
    Returns:
        Implied volatility as decimal (e.g., 0.20 for 20%)
    """
    if option_price <= 0 or time_to_expiry <= 0:
        return 0
    
    # Initial guess based on option moneyness
    if option_type.upper() == "CE":
        intrinsic = max(0, spot - strike)
    else:
        intrinsic = max(0, strike - spot)
    
    # Start with reasonable initial guess
    iv = 0.3  # 30% initial guess
    
    for _ in range(max_iterations):
        price = black_scholes_price(spot, strike, time_to_expiry, rate, iv, option_type, dividend)
        vega = calculate_vega(spot, strike, time_to_expiry, rate, iv, dividend)
        
        if vega < 0.0001:
            # Vega too small, can't converge
            break
        
        diff = price - option_price
        
        if abs(diff) < tolerance:
            break
        
        # Newton-Raphson update
        iv = iv - diff / vega
        
        # Keep IV in reasonable bounds
        iv = max(0.01, min(5.0, iv))
    
    return iv


def calculate_delta(
    spot: float,
    strike: float,
    time_to_expiry: float,
    rate: float,
    volatility: float,
    option_type: str,
    dividend: float = 0
) -> float:
    """
    Calculate option Delta.
    
    Delta measures the rate of change of option price with respect to
    changes in the underlying asset's price.
    
    Returns:
        Delta value (-1 to 1)
    """
    if time_to_expiry <= 0:
        if option_type.upper() == "CE":
            return 1.0 if spot > strike else 0.0
        else:
            return -1.0 if spot < strike else 0.0
    
    d1, _ = calculate_d1_d2(spot, strike, time_to_expiry, rate, volatility, dividend)
    dividend_discount = math.exp(-dividend * time_to_expiry)
    
    if option_type.upper() == "CE":
        return dividend_discount * norm_cdf(d1)
    else:
        return dividend_discount * (norm_cdf(d1) - 1)


def calculate_gamma(
    spot: float,
    strike: float,
    time_to_expiry: float,
    rate: float,
    volatility: float,
    dividend: float = 0
) -> float:
    """
    Calculate option Gamma.
    
    Gamma measures the rate of change of Delta with respect to
    changes in the underlying price.
    
    Returns:
        Gamma value (always positive)
    """
    if time_to_expiry <= 0 or volatility <= 0 or spot <= 0:
        return 0
    
    d1, _ = calculate_d1_d2(spot, strike, time_to_expiry, rate, volatility, dividend)
    dividend_discount = math.exp(-dividend * time_to_expiry)
    
    return dividend_discount * norm_pdf(d1) / (spot * volatility * math.sqrt(time_to_expiry))


def calculate_theta(
    spot: float,
    strike: float,
    time_to_expiry: float,
    rate: float,
    volatility: float,
    option_type: str,
    dividend: float = 0
) -> float:
    """
    Calculate option Theta (per day).
    
    Theta measures the rate of change of option price with respect to time.
    
    Returns:
        Theta value (usually negative, per day)
    """
    if time_to_expiry <= 0:
        return 0
    
    d1, d2 = calculate_d1_d2(spot, strike, time_to_expiry, rate, volatility, dividend)
    
    sqrt_t = math.sqrt(time_to_expiry)
    discount = math.exp(-rate * time_to_expiry)
    dividend_discount = math.exp(-dividend * time_to_expiry)
    
    # First term (common to both)
    term1 = -(spot * dividend_discount * norm_pdf(d1) * volatility) / (2 * sqrt_t)
    
    if option_type.upper() == "CE":
        term2 = dividend * spot * dividend_discount * norm_cdf(d1)
        term3 = -rate * strike * discount * norm_cdf(d2)
        theta = term1 + term2 + term3
    else:
        term2 = -dividend * spot * dividend_discount * norm_cdf(-d1)
        term3 = rate * strike * discount * norm_cdf(-d2)
        theta = term1 + term2 + term3
    
    # Convert to per-day theta
    return theta / DAYS_IN_YEAR


def calculate_vega(
    spot: float,
    strike: float,
    time_to_expiry: float,
    rate: float,
    volatility: float,
    dividend: float = 0
) -> float:
    """
    Calculate option Vega.
    
    Vega measures the rate of change of option price with respect to
    changes in volatility.
    
    Returns:
        Vega value (per 1% change in volatility)
    """
    if time_to_expiry <= 0:
        return 0
    
    d1, _ = calculate_d1_d2(spot, strike, time_to_expiry, rate, volatility, dividend)
    dividend_discount = math.exp(-dividend * time_to_expiry)
    
    # Vega per 1% change
    return spot * dividend_discount * norm_pdf(d1) * math.sqrt(time_to_expiry) / 100


def calculate_greeks(
    spot: float,
    strike: float,
    expiry_days: float,
    rate: float,
    option_type: str,
    option_price: Optional[float] = None,
    volatility: Optional[float] = None,
    dividend: float = 0
) -> Greeks:
    """
    Calculate all Greeks for an option.
    
    Args:
        spot: Underlying spot price
        strike: Option strike price
        expiry_days: Days to expiry
        rate: Risk-free rate (annual, decimal, e.g., 0.07 for 7%)
        option_type: "CE" for call, "PE" for put
        option_price: Market price (for IV calculation)
        volatility: Known volatility (if not calculating IV)
        dividend: Dividend yield (annual, decimal)
    
    Returns:
        Greeks object with delta, gamma, theta, vega, iv
    """
    time_to_expiry = expiry_days / DAYS_IN_YEAR
    
    # Calculate or use provided IV
    if volatility is not None:
        iv = volatility
    elif option_price is not None and option_price > 0:
        iv = calculate_iv(option_price, spot, strike, time_to_expiry, rate, option_type, dividend)
    else:
        iv = 0.2  # Default 20% if no price provided
    
    # Calculate Greeks
    delta = calculate_delta(spot, strike, time_to_expiry, rate, iv, option_type, dividend)
    gamma = calculate_gamma(spot, strike, time_to_expiry, rate, iv, dividend)
    theta = calculate_theta(spot, strike, time_to_expiry, rate, iv, option_type, dividend)
    vega = calculate_vega(spot, strike, time_to_expiry, rate, iv, dividend)
    
    return Greeks(
        delta=round(delta, 4),
        gamma=round(gamma, 6),
        theta=round(theta, 4),
        vega=round(vega, 4),
        iv=round(iv * 100, 2)  # Convert to percentage
    )


def calculate_greeks_batch(
    options: list,
    spot: float,
    rate: float = 0.07,
    dividend: float = 0
) -> list:
    """
    Calculate Greeks for multiple options.
    
    Args:
        options: List of dicts with strike, expiry_days, option_type, option_price
        spot: Underlying spot price
        rate: Risk-free rate
        dividend: Dividend yield
    
    Returns:
        List of Greeks objects
    """
    results = []
    
    for opt in options:
        greeks = calculate_greeks(
            spot=spot,
            strike=opt.get("strike", 0),
            expiry_days=opt.get("expiry_days", 0),
            rate=rate,
            option_type=opt.get("option_type", "CE"),
            option_price=opt.get("option_price"),
            dividend=dividend
        )
        results.append(greeks)
    
    return results
