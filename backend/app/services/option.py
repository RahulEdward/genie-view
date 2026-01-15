"""
Option Service
Handles option chain, expiry dates, and ATM identification
"""

import json
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, delete

from app.brokers.base import BrokerAdapter, OptionData
from app.models.database import CachedOptionChain
from app.utils.cache import option_chain_cache
from app.utils.logger import logger
from app.config import settings


class OptionService:
    """Service for option chain operations"""
    
    def __init__(self, broker: BrokerAdapter, db: Optional[AsyncSession] = None):
        self.broker = broker
        self.db = db
        # Default TTL: 30 seconds
        self.cache_ttl = getattr(settings, 'OPTION_CHAIN_CACHE_TTL', 30)
    
    async def get_option_chain(
        self,
        underlying: str,
        exchange: str,
        expiry: Optional[str] = None,
        num_strikes: int = 10
    ) -> Dict[str, Any]:
        """
        Get option chain with ATM identification.
        
        Uses two-tier caching:
        1. Redis cache for fast access (short TTL)
        2. Database cache for persistence (configurable TTL)
        
        Args:
            underlying: Underlying symbol (NIFTY, BANKNIFTY, etc.)
            exchange: Exchange code (NFO, BFO)
            expiry: Optional expiry date in DDMMMYY format
            num_strikes: Number of strikes above/below ATM
        
        Returns:
            Dict with underlying info, ATM strike, and chain data
        """
        cache_key = f"{underlying}:{exchange}:{expiry or 'all'}:{num_strikes}"
        
        # Check Redis cache first (fastest)
        cached = await option_chain_cache.get(cache_key)
        if cached:
            logger.debug(f"Option chain Redis cache hit: {cache_key}")
            return cached
        
        # Check database cache (if db available)
        if self.db:
            db_cached = await self._get_from_db_cache(underlying, exchange, expiry)
            if db_cached:
                logger.debug(f"Option chain DB cache hit: {cache_key}")
                # Also set in Redis for faster subsequent access
                await option_chain_cache.set(cache_key, db_cached, ttl=self.cache_ttl)
                return db_cached
        
        # Fetch from broker
        chain_data = await self.broker.get_option_chain(underlying, exchange, expiry)
        
        if not chain_data or "options" not in chain_data:
            return {
                "underlying": underlying,
                "exchange": exchange,
                "spot_price": 0,
                "atm_strike": 0,
                "expiry": expiry,
                "calls": [],
                "puts": []
            }
        
        spot_price = chain_data.get("spot_price", 0)
        options = chain_data.get("options", [])
        
        # Identify ATM strike
        atm_strike = self.identify_atm_strike(spot_price, options)
        
        # Filter strikes around ATM
        filtered_options = self.filter_strikes_around_atm(
            options, atm_strike, num_strikes
        )
        
        # Separate calls and puts
        calls = [opt for opt in filtered_options if opt.get("option_type") == "CE"]
        puts = [opt for opt in filtered_options if opt.get("option_type") == "PE"]
        
        # Sort by strike
        calls.sort(key=lambda x: x.get("strike", 0))
        puts.sort(key=lambda x: x.get("strike", 0))
        
        result = {
            "underlying": underlying,
            "exchange": exchange,
            "spot_price": spot_price,
            "atm_strike": atm_strike,
            "expiry": expiry or chain_data.get("expiry"),
            "calls": calls,
            "puts": puts
        }
        
        # Cache in Redis
        await option_chain_cache.set(cache_key, result, ttl=self.cache_ttl)
        
        # Cache in database (if available)
        if self.db:
            await self._store_in_db_cache(underlying, exchange, expiry, result)
        
        return result
    
    async def _get_from_db_cache(
        self,
        underlying: str,
        exchange: str,
        expiry: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """
        Get option chain from database cache if not expired.
        
        Args:
            underlying: Underlying symbol
            exchange: Exchange code
            expiry: Expiry date
        
        Returns:
            Cached data if valid, None if expired or not found
        """
        try:
            now = datetime.utcnow()
            
            result = await self.db.execute(
                select(CachedOptionChain).where(
                    and_(
                        CachedOptionChain.underlying == underlying,
                        CachedOptionChain.exchange == exchange,
                        CachedOptionChain.expiry == (expiry or "all"),
                        CachedOptionChain.expires_at > now
                    )
                )
            )
            
            row = result.scalar_one_or_none()
            
            if row and row.data:
                return json.loads(row.data)
            
            return None
            
        except Exception as e:
            logger.warning(f"DB cache read error: {e}")
            return None
    
    async def _store_in_db_cache(
        self,
        underlying: str,
        exchange: str,
        expiry: Optional[str],
        data: Dict[str, Any]
    ) -> None:
        """
        Store option chain in database cache with TTL.
        
        Args:
            underlying: Underlying symbol
            exchange: Exchange code
            expiry: Expiry date
            data: Option chain data to cache
        """
        try:
            now = datetime.utcnow()
            expires_at = now + timedelta(seconds=self.cache_ttl)
            expiry_key = expiry or "all"
            
            # Check if exists
            result = await self.db.execute(
                select(CachedOptionChain).where(
                    and_(
                        CachedOptionChain.underlying == underlying,
                        CachedOptionChain.exchange == exchange,
                        CachedOptionChain.expiry == expiry_key
                    )
                )
            )
            
            row = result.scalar_one_or_none()
            
            if row:
                # Update existing
                row.data = json.dumps(data)
                row.created_at = now
                row.expires_at = expires_at
            else:
                # Insert new
                new_row = CachedOptionChain(
                    underlying=underlying,
                    exchange=exchange,
                    expiry=expiry_key,
                    data=json.dumps(data),
                    created_at=now,
                    expires_at=expires_at
                )
                self.db.add(new_row)
            
            await self.db.commit()
            
        except Exception as e:
            logger.warning(f"DB cache write error: {e}")
            await self.db.rollback()
    
    async def cleanup_expired_cache(self) -> int:
        """
        Remove expired cache entries from database.
        
        Returns:
            Number of deleted entries
        """
        if not self.db:
            return 0
        
        try:
            now = datetime.utcnow()
            
            result = await self.db.execute(
                delete(CachedOptionChain).where(
                    CachedOptionChain.expires_at <= now
                )
            )
            
            await self.db.commit()
            
            deleted = result.rowcount
            if deleted > 0:
                logger.info(f"Cleaned up {deleted} expired option chain cache entries")
            
            return deleted
            
        except Exception as e:
            logger.warning(f"Cache cleanup error: {e}")
            await self.db.rollback()
            return 0
    
    async def get_expiry_dates(
        self,
        underlying: str,
        exchange: str,
        instrument_type: str = "options"
    ) -> List[str]:
        """
        Get available expiry dates.
        
        Args:
            underlying: Underlying symbol
            exchange: Exchange code
            instrument_type: "options" or "futures"
        
        Returns:
            List of expiry dates in DD-MMM-YY format, sorted ascending
        """
        # First try broker's direct expiry API
        expiries = await self.broker.get_expiry_dates(
            underlying, exchange, instrument_type
        )
        
        # If no expiries from broker, try to extract from symbol search
        if not expiries:
            expiries = await self._extract_expiries_from_search(
                underlying, exchange, instrument_type
            )
        
        # Sort by date
        return self.sort_expiries(expiries)
    
    async def _extract_expiries_from_search(
        self,
        underlying: str,
        exchange: str,
        instrument_type: str
    ) -> List[str]:
        """
        Extract expiry dates from symbol search results.
        
        Angel One doesn't have a direct expiry API, so we search for
        option/future symbols and extract unique expiry dates.
        
        Args:
            underlying: Underlying symbol
            exchange: Exchange code
            instrument_type: "options" or "futures"
        
        Returns:
            List of unique expiry dates
        """
        import re
        
        try:
            # Search for symbols
            results = await self.broker.search_symbols(underlying, exchange)
            
            if not results:
                return []
            
            expiries = set()
            
            # Pattern to extract expiry from symbol names
            # Examples: RELIANCE24FEB261000CE, NIFTY30JAN25CE, BANKNIFTY24JAN2550000CE
            # Format: SYMBOL + DDMMMYY + STRIKE + CE/PE
            expiry_pattern = re.compile(
                r'(\d{2}[A-Z]{3}\d{2})',  # DDMMMYY format
                re.IGNORECASE
            )
            
            for result in results:
                symbol = result.symbol if hasattr(result, 'symbol') else result.get('symbol', '')
                
                # Filter by instrument type
                if instrument_type == "options":
                    if not (symbol.endswith('CE') or symbol.endswith('PE')):
                        continue
                elif instrument_type == "futures":
                    if symbol.endswith('CE') or symbol.endswith('PE'):
                        continue
                
                # Extract expiry date
                match = expiry_pattern.search(symbol)
                if match:
                    expiry = match.group(1).upper()
                    # Convert to DD-MMM-YY format
                    formatted = f"{expiry[:2]}-{expiry[2:5]}-{expiry[5:]}"
                    expiries.add(formatted)
            
            return list(expiries)
            
        except Exception as e:
            logger.warning(f"Error extracting expiries from search: {e}")
            return []
    
    def identify_atm_strike(
        self,
        spot_price: float,
        options: List[Dict]
    ) -> float:
        """
        Identify ATM (At-The-Money) strike.
        
        ATM strike is the strike price closest to the current spot price.
        
        Args:
            spot_price: Current underlying price
            options: List of option data dicts
        
        Returns:
            ATM strike price
        """
        if not options or spot_price <= 0:
            return 0
        
        # Get unique strikes
        strikes = set()
        for opt in options:
            strike = opt.get("strike", 0)
            if strike > 0:
                strikes.add(strike)
        
        if not strikes:
            return 0
        
        # Find closest strike to spot
        return min(strikes, key=lambda x: abs(x - spot_price))
    
    def filter_strikes_around_atm(
        self,
        options: List[Dict],
        atm_strike: float,
        num_strikes: int
    ) -> List[Dict]:
        """
        Filter options to include only strikes around ATM.
        
        Args:
            options: All option data
            atm_strike: ATM strike price
            num_strikes: Number of strikes above/below ATM
        
        Returns:
            Filtered options list
        """
        if not options or atm_strike <= 0:
            return options
        
        # Get unique strikes sorted
        strikes = sorted(set(opt.get("strike", 0) for opt in options if opt.get("strike", 0) > 0))
        
        if not strikes:
            return options
        
        # Find ATM index
        try:
            atm_idx = strikes.index(atm_strike)
        except ValueError:
            # ATM not in list, find closest
            atm_idx = min(range(len(strikes)), key=lambda i: abs(strikes[i] - atm_strike))
        
        # Get strike range
        start_idx = max(0, atm_idx - num_strikes)
        end_idx = min(len(strikes), atm_idx + num_strikes + 1)
        
        valid_strikes = set(strikes[start_idx:end_idx])
        
        # Filter options
        return [opt for opt in options if opt.get("strike", 0) in valid_strikes]
    
    def sort_expiries(self, expiries: List[str]) -> List[str]:
        """
        Sort expiry dates chronologically.
        
        Args:
            expiries: List of expiry strings in DD-MMM-YY or DDMMMYY format
        
        Returns:
            Sorted list of expiries
        """
        def parse_expiry(exp: str) -> datetime:
            """Parse expiry to datetime"""
            # Remove any dashes for consistent parsing
            exp_clean = exp.upper().replace("-", "")
            
            try:
                return datetime.strptime(exp_clean, "%d%b%y")
            except ValueError:
                pass
            
            # Try other formats
            for fmt in ["%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d%b%Y"]:
                try:
                    return datetime.strptime(exp, fmt)
                except ValueError:
                    continue
            
            # Return far future date for unparseable
            return datetime(2099, 12, 31)
        
        return sorted(expiries, key=parse_expiry)
    
    def get_strike_step(self, underlying: str) -> float:
        """
        Get strike step size for an underlying.
        
        Args:
            underlying: Underlying symbol
        
        Returns:
            Strike step size
        """
        # Standard strike steps for Indian indices
        strike_steps = {
            "NIFTY": 50,
            "BANKNIFTY": 100,
            "FINNIFTY": 50,
            "MIDCPNIFTY": 25,
            "SENSEX": 100,
            "BANKEX": 100,
        }
        
        return strike_steps.get(underlying.upper(), 100)
    
    def round_to_strike(self, price: float, underlying: str) -> float:
        """
        Round price to nearest valid strike.
        
        Args:
            price: Price to round
            underlying: Underlying symbol
        
        Returns:
            Rounded strike price
        """
        step = self.get_strike_step(underlying)
        return round(price / step) * step


def identify_atm_strike(spot_price: float, strikes: List[float]) -> float:
    """
    Identify ATM strike from a list of strikes.
    
    Args:
        spot_price: Current spot price
        strikes: List of available strikes
    
    Returns:
        ATM strike (closest to spot)
    """
    if not strikes or spot_price <= 0:
        return 0
    
    return min(strikes, key=lambda x: abs(x - spot_price))


def filter_option_chain_by_expiry(
    options: List[Dict],
    expiry: str
) -> List[Dict]:
    """
    Filter option chain to specific expiry.
    
    Args:
        options: All options
        expiry: Target expiry in DDMMMYY format
    
    Returns:
        Filtered options for that expiry
    """
    expiry_upper = expiry.upper()
    return [
        opt for opt in options
        if opt.get("expiry", "").upper() == expiry_upper
    ]
