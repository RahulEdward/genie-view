"""
Market Timing Service
Handles market hours, holidays, and trading status
"""

from typing import List, Dict, Optional
from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo

from app.utils.cache import market_cache
from app.utils.logger import logger


# IST timezone
IST = ZoneInfo("Asia/Kolkata")


# Market timing configurations
MARKET_TIMINGS = {
    "NSE": {
        "pre_open_start": time(9, 0),
        "pre_open_end": time(9, 8),
        "market_open": time(9, 15),
        "market_close": time(15, 30),
        "post_close_end": time(16, 0),
        "days": [0, 1, 2, 3, 4],  # Monday to Friday
    },
    "BSE": {
        "pre_open_start": time(9, 0),
        "pre_open_end": time(9, 8),
        "market_open": time(9, 15),
        "market_close": time(15, 30),
        "post_close_end": time(16, 0),
        "days": [0, 1, 2, 3, 4],
    },
    "NFO": {
        "market_open": time(9, 15),
        "market_close": time(15, 30),
        "days": [0, 1, 2, 3, 4],
    },
    "BFO": {
        "market_open": time(9, 15),
        "market_close": time(15, 30),
        "days": [0, 1, 2, 3, 4],
    },
    "MCX": {
        "market_open": time(9, 0),
        "market_close": time(23, 30),
        "days": [0, 1, 2, 3, 4],
    },
    "CDS": {
        "market_open": time(9, 0),
        "market_close": time(17, 0),
        "days": [0, 1, 2, 3, 4],
    },
}


# NSE/BSE holidays for 2025-2026 (sample - should be updated annually)
HOLIDAYS_2025 = [
    date(2025, 1, 26),   # Republic Day
    date(2025, 2, 26),   # Mahashivratri
    date(2025, 3, 14),   # Holi
    date(2025, 3, 31),   # Id-Ul-Fitr
    date(2025, 4, 10),   # Shri Mahavir Jayanti
    date(2025, 4, 14),   # Dr. Ambedkar Jayanti
    date(2025, 4, 18),   # Good Friday
    date(2025, 5, 1),    # Maharashtra Day
    date(2025, 8, 15),   # Independence Day
    date(2025, 8, 27),   # Janmashtami
    date(2025, 10, 2),   # Gandhi Jayanti
    date(2025, 10, 21),  # Diwali Laxmi Pujan
    date(2025, 10, 22),  # Diwali Balipratipada
    date(2025, 11, 5),   # Guru Nanak Jayanti
    date(2025, 12, 25),  # Christmas
]

HOLIDAYS_2026 = [
    date(2026, 1, 26),   # Republic Day
    date(2026, 3, 10),   # Holi
    date(2026, 4, 3),    # Good Friday
    date(2026, 4, 14),   # Dr. Ambedkar Jayanti
    date(2026, 5, 1),    # Maharashtra Day
    date(2026, 8, 15),   # Independence Day
    date(2026, 10, 2),   # Gandhi Jayanti
    date(2026, 11, 9),   # Diwali
    date(2026, 12, 25),  # Christmas
]


class MarketTimingService:
    """Service for market timing and holiday information"""
    
    def __init__(self):
        self.holidays = set(HOLIDAYS_2025 + HOLIDAYS_2026)
    
    async def get_timings(self, exchange: str) -> Dict:
        """
        Get market timings for an exchange.
        
        Args:
            exchange: Exchange code (NSE, BSE, NFO, etc.)
        
        Returns:
            Dict with market timing details
        """
        exchange_upper = exchange.upper()
        
        if exchange_upper not in MARKET_TIMINGS:
            return {
                "exchange": exchange_upper,
                "error": f"Unknown exchange: {exchange_upper}",
                "supported_exchanges": list(MARKET_TIMINGS.keys())
            }
        
        timings = MARKET_TIMINGS[exchange_upper]
        
        return {
            "exchange": exchange_upper,
            "pre_open_start": timings.get("pre_open_start", timings["market_open"]).strftime("%H:%M"),
            "pre_open_end": timings.get("pre_open_end", timings["market_open"]).strftime("%H:%M"),
            "market_open": timings["market_open"].strftime("%H:%M"),
            "market_close": timings["market_close"].strftime("%H:%M"),
            "post_close_end": timings.get("post_close_end", timings["market_close"]).strftime("%H:%M"),
            "trading_days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
            "timezone": "Asia/Kolkata"
        }
    
    async def get_holidays(
        self,
        year: Optional[int] = None,
        exchange: str = "NSE"
    ) -> List[Dict]:
        """
        Get list of market holidays.
        
        Args:
            year: Year to get holidays for (default: current year)
            exchange: Exchange code
        
        Returns:
            List of holiday dicts with date and description
        """
        if year is None:
            year = datetime.now(IST).year
        
        # Filter holidays for the year
        year_holidays = [h for h in self.holidays if h.year == year]
        year_holidays.sort()
        
        return [
            {
                "date": h.strftime("%Y-%m-%d"),
                "day": h.strftime("%A"),
                "exchange": exchange.upper()
            }
            for h in year_holidays
        ]
    
    async def is_market_open(
        self,
        exchange: str = "NSE",
        check_time: Optional[datetime] = None
    ) -> Dict:
        """
        Check if market is currently open.
        
        Args:
            exchange: Exchange code
            check_time: Time to check (default: current time)
        
        Returns:
            Dict with market status and details
        """
        exchange_upper = exchange.upper()
        
        if exchange_upper not in MARKET_TIMINGS:
            return {
                "exchange": exchange_upper,
                "is_open": False,
                "status": "UNKNOWN_EXCHANGE",
                "message": f"Unknown exchange: {exchange_upper}"
            }
        
        # Get current IST time
        if check_time is None:
            now = datetime.now(IST)
        else:
            now = check_time if check_time.tzinfo else check_time.replace(tzinfo=IST)
        
        current_date = now.date()
        current_time = now.time()
        
        timings = MARKET_TIMINGS[exchange_upper]
        
        # Check if weekend
        if now.weekday() not in timings["days"]:
            return {
                "exchange": exchange_upper,
                "is_open": False,
                "status": "WEEKEND",
                "message": "Market closed - Weekend",
                "next_open": self._get_next_trading_day(current_date, exchange_upper)
            }
        
        # Check if holiday
        if current_date in self.holidays:
            return {
                "exchange": exchange_upper,
                "is_open": False,
                "status": "HOLIDAY",
                "message": "Market closed - Holiday",
                "next_open": self._get_next_trading_day(current_date, exchange_upper)
            }
        
        # Check market hours
        market_open = timings["market_open"]
        market_close = timings["market_close"]
        pre_open_start = timings.get("pre_open_start", market_open)
        
        if current_time < pre_open_start:
            return {
                "exchange": exchange_upper,
                "is_open": False,
                "status": "PRE_MARKET",
                "message": f"Market opens at {market_open.strftime('%H:%M')} IST",
                "opens_at": market_open.strftime("%H:%M")
            }
        
        if pre_open_start <= current_time < market_open:
            return {
                "exchange": exchange_upper,
                "is_open": False,
                "status": "PRE_OPEN",
                "message": "Pre-open session in progress",
                "opens_at": market_open.strftime("%H:%M")
            }
        
        if market_open <= current_time <= market_close:
            return {
                "exchange": exchange_upper,
                "is_open": True,
                "status": "OPEN",
                "message": "Market is open",
                "closes_at": market_close.strftime("%H:%M")
            }
        
        return {
            "exchange": exchange_upper,
            "is_open": False,
            "status": "CLOSED",
            "message": f"Market closed at {market_close.strftime('%H:%M')} IST",
            "next_open": self._get_next_trading_day(current_date, exchange_upper)
        }
    
    def _get_next_trading_day(self, from_date: date, exchange: str) -> str:
        """Get next trading day"""
        timings = MARKET_TIMINGS.get(exchange, MARKET_TIMINGS["NSE"])
        
        next_day = from_date + timedelta(days=1)
        
        # Find next valid trading day
        for _ in range(10):  # Max 10 days ahead
            if next_day.weekday() in timings["days"] and next_day not in self.holidays:
                return next_day.strftime("%Y-%m-%d")
            next_day += timedelta(days=1)
        
        return next_day.strftime("%Y-%m-%d")
    
    def is_trading_day(self, check_date: date, exchange: str = "NSE") -> bool:
        """
        Check if a date is a trading day.
        
        Args:
            check_date: Date to check
            exchange: Exchange code
        
        Returns:
            True if trading day
        """
        exchange_upper = exchange.upper()
        timings = MARKET_TIMINGS.get(exchange_upper, MARKET_TIMINGS["NSE"])
        
        # Check weekend
        if check_date.weekday() not in timings["days"]:
            return False
        
        # Check holiday
        if check_date in self.holidays:
            return False
        
        return True
    
    def add_holiday(self, holiday_date: date) -> None:
        """Add a holiday to the list"""
        self.holidays.add(holiday_date)
    
    def remove_holiday(self, holiday_date: date) -> None:
        """Remove a holiday from the list"""
        self.holidays.discard(holiday_date)


def is_market_open(
    exchange: str = "NSE",
    check_time: Optional[datetime] = None,
    holidays: Optional[set] = None
) -> bool:
    """
    Simple function to check if market is open.
    
    Args:
        exchange: Exchange code
        check_time: Time to check
        holidays: Set of holiday dates
    
    Returns:
        True if market is open
    """
    exchange_upper = exchange.upper()
    
    if exchange_upper not in MARKET_TIMINGS:
        return False
    
    if check_time is None:
        now = datetime.now(IST)
    else:
        now = check_time if check_time.tzinfo else check_time.replace(tzinfo=IST)
    
    timings = MARKET_TIMINGS[exchange_upper]
    
    # Check weekend
    if now.weekday() not in timings["days"]:
        return False
    
    # Check holiday
    if holidays and now.date() in holidays:
        return False
    
    # Check time
    current_time = now.time()
    return timings["market_open"] <= current_time <= timings["market_close"]


def get_trading_days_between(
    start_date: date,
    end_date: date,
    exchange: str = "NSE",
    holidays: Optional[set] = None
) -> List[date]:
    """
    Get list of trading days between two dates.
    
    Args:
        start_date: Start date
        end_date: End date
        exchange: Exchange code
        holidays: Set of holiday dates
    
    Returns:
        List of trading dates
    """
    if holidays is None:
        holidays = set(HOLIDAYS_2025 + HOLIDAYS_2026)
    
    timings = MARKET_TIMINGS.get(exchange.upper(), MARKET_TIMINGS["NSE"])
    
    trading_days = []
    current = start_date
    
    while current <= end_date:
        if current.weekday() in timings["days"] and current not in holidays:
            trading_days.append(current)
        current += timedelta(days=1)
    
    return trading_days
