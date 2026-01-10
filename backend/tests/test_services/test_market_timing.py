"""
Market Timing Service Tests
Property-based and unit tests for market timing
"""

import pytest
from hypothesis import given, strategies as st, settings
from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo

from app.services.market_timing import (
    MarketTimingService, is_market_open, get_trading_days_between,
    MARKET_TIMINGS, HOLIDAYS_2025, IST
)


# ==================== Property Tests ====================

class TestMarketOpenStatus:
    """
    Property 12: Market Open/Closed Status
    For any given time, market status SHALL be correctly determined based on
    exchange timings and holiday calendar.
    Validates: Requirements 8.1, 8.3
    """
    
    @given(
        st.sampled_from(["NSE", "BSE", "NFO"]),
        st.integers(min_value=0, max_value=4),  # Monday to Friday
        st.integers(min_value=9, max_value=15),  # Hours 9-15
        st.integers(min_value=15, max_value=30),  # Minutes 15-30
    )
    @settings(max_examples=100)
    def test_market_open_during_trading_hours(self, exchange, weekday, hour, minute):
        """
        Property: Market is open during trading hours on trading days.
        """
        # Create a datetime on a weekday during market hours
        # Find next occurrence of this weekday
        today = date(2025, 1, 6)  # A Monday
        days_ahead = weekday - today.weekday()
        if days_ahead < 0:
            days_ahead += 7
        target_date = today + timedelta(days=days_ahead)
        
        # Skip if it's a holiday
        if target_date in set(HOLIDAYS_2025):
            return
        
        # Create time during market hours (9:15 to 15:30)
        if hour == 9 and minute < 15:
            minute = 15
        if hour == 15 and minute > 30:
            minute = 30
        
        check_time = datetime(target_date.year, target_date.month, target_date.day, hour, minute, tzinfo=IST)
        
        result = is_market_open(exchange, check_time, set(HOLIDAYS_2025))
        
        # Should be open during trading hours
        timings = MARKET_TIMINGS[exchange]
        market_open = timings["market_open"]
        market_close = timings["market_close"]
        
        if market_open <= check_time.time() <= market_close:
            assert result is True, f"Market should be open at {check_time}"
    
    @given(
        st.sampled_from(["NSE", "BSE", "NFO"]),
        st.integers(min_value=5, max_value=6),  # Saturday, Sunday
    )
    @settings(max_examples=50)
    def test_market_closed_on_weekends(self, exchange, weekday):
        """
        Property: Market is always closed on weekends.
        """
        # Find next occurrence of this weekend day
        today = date(2025, 1, 6)  # A Monday
        days_ahead = weekday - today.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        target_date = today + timedelta(days=days_ahead)
        
        check_time = datetime(target_date.year, target_date.month, target_date.day, 12, 0, tzinfo=IST)
        
        result = is_market_open(exchange, check_time)
        
        assert result is False, f"Market should be closed on weekend: {check_time}"
    
    @given(st.sampled_from(HOLIDAYS_2025))
    @settings(max_examples=50)
    def test_market_closed_on_holidays(self, holiday):
        """
        Property: Market is always closed on holidays.
        """
        check_time = datetime(holiday.year, holiday.month, holiday.day, 12, 0, tzinfo=IST)
        
        result = is_market_open("NSE", check_time, set(HOLIDAYS_2025))
        
        assert result is False, f"Market should be closed on holiday: {holiday}"
    
    @given(
        st.sampled_from(["NSE", "BSE", "NFO"]),
        st.integers(min_value=0, max_value=4),  # Weekday
        st.integers(min_value=16, max_value=23),  # After market hours
    )
    @settings(max_examples=50)
    def test_market_closed_after_hours(self, exchange, weekday, hour):
        """
        Property: Market is closed after trading hours.
        """
        today = date(2025, 1, 6)
        days_ahead = weekday - today.weekday()
        if days_ahead < 0:
            days_ahead += 7
        target_date = today + timedelta(days=days_ahead)
        
        if target_date in set(HOLIDAYS_2025):
            return
        
        check_time = datetime(target_date.year, target_date.month, target_date.day, hour, 0, tzinfo=IST)
        
        result = is_market_open(exchange, check_time, set(HOLIDAYS_2025))
        
        assert result is False, f"Market should be closed at {hour}:00"


class TestTradingDays:
    """Test trading days calculation"""
    
    @given(
        st.dates(min_value=date(2025, 1, 1), max_value=date(2025, 12, 31)),
        st.integers(min_value=1, max_value=30)
    )
    @settings(max_examples=100)
    def test_trading_days_excludes_weekends(self, start_date, num_days):
        """
        Property: Trading days never include weekends.
        """
        end_date = start_date + timedelta(days=num_days)
        
        trading_days = get_trading_days_between(start_date, end_date, "NSE", set(HOLIDAYS_2025))
        
        for day in trading_days:
            assert day.weekday() < 5, f"Weekend found in trading days: {day}"
    
    @given(
        st.dates(min_value=date(2025, 1, 1), max_value=date(2025, 12, 31)),
        st.integers(min_value=1, max_value=30)
    )
    @settings(max_examples=100)
    def test_trading_days_excludes_holidays(self, start_date, num_days):
        """
        Property: Trading days never include holidays.
        """
        end_date = start_date + timedelta(days=num_days)
        holidays = set(HOLIDAYS_2025)
        
        trading_days = get_trading_days_between(start_date, end_date, "NSE", holidays)
        
        for day in trading_days:
            assert day not in holidays, f"Holiday found in trading days: {day}"
    
    @given(
        st.dates(min_value=date(2025, 1, 1), max_value=date(2025, 6, 30)),
        st.integers(min_value=1, max_value=60)
    )
    @settings(max_examples=100)
    def test_trading_days_count_reasonable(self, start_date, num_days):
        """
        Property: Trading days count is less than or equal to calendar days.
        """
        end_date = start_date + timedelta(days=num_days)
        
        trading_days = get_trading_days_between(start_date, end_date, "NSE", set(HOLIDAYS_2025))
        
        assert len(trading_days) <= num_days + 1


# ==================== Unit Tests ====================

class TestMarketTimingService:
    """Unit tests for MarketTimingService"""
    
    @pytest.fixture
    def service(self):
        return MarketTimingService()
    
    @pytest.mark.asyncio
    async def test_get_timings_nse(self, service):
        """Get NSE timings"""
        timings = await service.get_timings("NSE")
        
        assert timings["exchange"] == "NSE"
        assert timings["market_open"] == "09:15"
        assert timings["market_close"] == "15:30"
        assert timings["timezone"] == "Asia/Kolkata"
    
    @pytest.mark.asyncio
    async def test_get_timings_unknown_exchange(self, service):
        """Unknown exchange returns error"""
        timings = await service.get_timings("UNKNOWN")
        
        assert "error" in timings
        assert "supported_exchanges" in timings
    
    @pytest.mark.asyncio
    async def test_get_holidays(self, service):
        """Get holidays for a year"""
        holidays = await service.get_holidays(2025, "NSE")
        
        assert len(holidays) > 0
        assert all("date" in h for h in holidays)
        assert all("day" in h for h in holidays)
    
    @pytest.mark.asyncio
    async def test_is_market_open_during_hours(self, service):
        """Market open during trading hours"""
        # Wednesday at 11:00 AM IST (not a holiday)
        check_time = datetime(2025, 1, 8, 11, 0, tzinfo=IST)
        
        result = await service.is_market_open("NSE", check_time)
        
        assert result["is_open"] is True
        assert result["status"] == "OPEN"
    
    @pytest.mark.asyncio
    async def test_is_market_open_before_hours(self, service):
        """Market closed before trading hours"""
        check_time = datetime(2025, 1, 8, 8, 0, tzinfo=IST)
        
        result = await service.is_market_open("NSE", check_time)
        
        assert result["is_open"] is False
        assert result["status"] == "PRE_MARKET"
    
    @pytest.mark.asyncio
    async def test_is_market_open_after_hours(self, service):
        """Market closed after trading hours"""
        check_time = datetime(2025, 1, 8, 17, 0, tzinfo=IST)
        
        result = await service.is_market_open("NSE", check_time)
        
        assert result["is_open"] is False
        assert result["status"] == "CLOSED"
    
    @pytest.mark.asyncio
    async def test_is_market_open_weekend(self, service):
        """Market closed on weekend"""
        # Saturday
        check_time = datetime(2025, 1, 11, 12, 0, tzinfo=IST)
        
        result = await service.is_market_open("NSE", check_time)
        
        assert result["is_open"] is False
        assert result["status"] == "WEEKEND"
    
    @pytest.mark.asyncio
    async def test_is_market_open_holiday(self, service):
        """Market closed on holiday"""
        # Republic Day
        check_time = datetime(2025, 1, 26, 12, 0, tzinfo=IST)
        
        result = await service.is_market_open("NSE", check_time)
        
        assert result["is_open"] is False
        assert result["status"] == "HOLIDAY"
    
    def test_is_trading_day(self, service):
        """Check if date is trading day"""
        # Regular Wednesday
        assert service.is_trading_day(date(2025, 1, 8), "NSE") is True
        
        # Saturday
        assert service.is_trading_day(date(2025, 1, 11), "NSE") is False
        
        # Holiday (Republic Day)
        assert service.is_trading_day(date(2025, 1, 26), "NSE") is False
    
    def test_add_remove_holiday(self, service):
        """Add and remove holidays"""
        new_holiday = date(2025, 12, 31)
        
        # Add holiday
        service.add_holiday(new_holiday)
        assert new_holiday in service.holidays
        
        # Remove holiday
        service.remove_holiday(new_holiday)
        assert new_holiday not in service.holidays


class TestHelperFunctions:
    """Unit tests for helper functions"""
    
    def test_is_market_open_simple(self):
        """Simple market open check"""
        # During market hours on a weekday
        check_time = datetime(2025, 1, 8, 12, 0, tzinfo=IST)
        
        result = is_market_open("NSE", check_time, set(HOLIDAYS_2025))
        
        assert result is True
    
    def test_get_trading_days_between(self):
        """Get trading days between dates"""
        start = date(2025, 1, 6)  # Monday
        end = date(2025, 1, 12)   # Sunday
        
        days = get_trading_days_between(start, end, "NSE", set(HOLIDAYS_2025))
        
        # Should be Mon-Fri (5 days)
        assert len(days) == 5
        assert all(d.weekday() < 5 for d in days)
    
    def test_get_trading_days_with_holiday(self):
        """Trading days excludes holidays"""
        # Week containing Republic Day (Jan 26)
        start = date(2025, 1, 20)
        end = date(2025, 1, 31)
        
        days = get_trading_days_between(start, end, "NSE", set(HOLIDAYS_2025))
        
        # Jan 26 should not be in the list
        assert date(2025, 1, 26) not in days
