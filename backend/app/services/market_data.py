"""
Market Data Service
Handles historical data, quotes, and caching
"""

from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.brokers.base import BrokerAdapter, OHLCCandle, Quote
from app.models.database import OHLCHistory
from app.utils.cache import history_cache, quote_cache
from app.utils.logger import logger
from app.config import settings


# IST offset in seconds
IST_OFFSET_SECONDS = 19800  # 5 hours 30 minutes


class MarketDataService:
    """Service for market data operations with caching"""
    
    def __init__(self, broker: BrokerAdapter, db: AsyncSession):
        self.broker = broker
        self.db = db
    
    async def get_history(
        self,
        symbol: str,
        exchange: str,
        interval: str,
        start_date: str,
        end_date: str
    ) -> List[Dict]:
        """
        Get historical OHLC data with caching.
        
        OPTIMIZED:
        1. Check Redis cache first (5 min TTL for faster repeated loads)
        2. Check database for stored data
        3. Fetch missing data from broker in parallel
        4. Store in database with bulk insert
        
        Args:
            symbol: Trading symbol
            exchange: Exchange code
            interval: Candle interval
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
        
        Returns:
            List of OHLC candles with IST timestamps
        """
        import asyncio
        
        cache_key = f"{symbol}:{exchange}:{interval}:{start_date}:{end_date}"
        
        # Check Redis cache first (increased TTL to 5 minutes)
        cached = await history_cache.get(cache_key)
        if cached:
            logger.debug(f"Cache hit for {cache_key}")
            return cached
        
        # Parse dates
        from_dt = datetime.strptime(start_date, "%Y-%m-%d")
        to_dt = datetime.strptime(end_date, "%Y-%m-%d")
        to_dt = to_dt.replace(hour=23, minute=59, second=59)
        
        # Get data from database
        db_candles = await self._get_from_db(symbol, exchange, interval, from_dt, to_dt)
        
        # If we have enough data in DB, return it immediately
        if db_candles:
            # For daily data, check if we have recent data
            last_candle_time = datetime.fromtimestamp(db_candles[-1].timestamp)
            now = datetime.now()
            
            # If last candle is from today or yesterday (market closed), use cached data
            if interval in ["1d", "1w", "1M", "ONE_DAY", "ONE_WEEK", "ONE_MONTH"]:
                if (now - last_candle_time).days <= 1:
                    output = [
                        {
                            "timestamp": c.timestamp + IST_OFFSET_SECONDS,
                            "open": c.open,
                            "high": c.high,
                            "low": c.low,
                            "close": c.close,
                            "volume": c.volume
                        }
                        for c in db_candles
                    ]
                    # Cache for 5 minutes
                    await history_cache.set(cache_key, output, ttl=300)
                    logger.info(f"History from DB: {symbol} returned {len(output)} candles")
                    return output
        
        # Find missing date ranges
        missing_ranges = self._find_missing_ranges(db_candles, from_dt, to_dt, interval)
        
        # Fetch missing data from broker
        all_candles = list(db_candles)
        
        if missing_ranges:
            # Fetch all missing ranges (could be parallelized for multiple ranges)
            for range_start, range_end in missing_ranges:
                logger.debug(f"Fetching missing data: {range_start} to {range_end}")
                
                try:
                    broker_candles = await self.broker.get_historical_data(
                        symbol, exchange, interval, range_start, range_end
                    )
                    
                    if broker_candles:
                        logger.info(f"Fetched {len(broker_candles)} candles from broker")
                        # Store in database (bulk insert - fast)
                        await self._store_candles(symbol, exchange, interval, broker_candles)
                        all_candles.extend(broker_candles)
                except Exception as e:
                    logger.warning(f"Failed to fetch data for {range_start} to {range_end}: {e}")
        
        # Sort and deduplicate
        all_candles.sort(key=lambda x: x.timestamp)
        result = self._deduplicate_candles(all_candles)
        
        # Convert to dict format with IST offset
        output = [
            {
                "timestamp": c.timestamp + IST_OFFSET_SECONDS,
                "open": c.open,
                "high": c.high,
                "low": c.low,
                "close": c.close,
                "volume": c.volume
            }
            for c in result
        ]
        
        # Cache for 5 minutes (increased from 1 minute)
        if output:
            await history_cache.set(cache_key, output, ttl=300)
        
        logger.info(f"History: {symbol} returned {len(output)} candles")
        return output
    
    async def get_quote(self, symbol: str, exchange: str) -> Dict:
        """
        Get current quote with change calculation.
        
        Args:
            symbol: Trading symbol
            exchange: Exchange code
        
        Returns:
            Quote data with change and change_percent
        """
        cache_key = f"{symbol}:{exchange}"
        
        try:
            quote = await self.broker.get_quote(symbol, exchange)
            
            # Calculate change
            change = quote.ltp - quote.prev_close
            change_percent = (change / quote.prev_close * 100) if quote.prev_close > 0 else 0
            
            result = {
                "ltp": quote.ltp,
                "open": quote.open,
                "high": quote.high,
                "low": quote.low,
                "prev_close": quote.prev_close,
                "volume": quote.volume,
                "change": round(change, 2),
                "change_percent": round(change_percent, 2)
            }
            
            # Cache quote for 5 seconds
            await quote_cache.set(cache_key, result, ttl=5)
            
            return result
            
        except Exception as e:
            logger.warning(f"Quote fetch failed for {symbol}: {e}")
            
            # Try to return cached quote with stale indicator
            cached = await quote_cache.get(cache_key)
            if cached:
                cached["stale"] = True
                return cached
            
            raise
    
    async def get_quotes_batch(self, symbols: List[Dict[str, str]]) -> Dict[str, Dict]:
        """
        Get quotes for multiple symbols with caching.
        
        Args:
            symbols: List of {symbol, exchange} dicts
        
        Returns:
            Dict mapping "SYMBOL:EXCHANGE" to Quote data dict
        """
        result = {}
        missing_symbols = []
        
        # Check cache for each symbol
        for item in symbols:
            symbol = item["symbol"]
            exchange = item.get("exchange", "NSE")
            key = f"{symbol}:{exchange}"
            
            cached = await quote_cache.get(key)
            if cached:
                result[key] = cached
            else:
                missing_symbols.append(item)
        
        # Fetch missing from broker
        if missing_symbols:
            try:
                broker_quotes = await self.broker.get_quotes_batch(missing_symbols)
                
                for key, quote in broker_quotes.items():
                    # Calculate change
                    change = quote.ltp - quote.prev_close
                    change_percent = (change / quote.prev_close * 100) if quote.prev_close > 0 else 0
                    
                    # Extract symbol info from key
                    parts = key.split(':')
                    sym = parts[0]
                    exch = parts[1] if len(parts) > 1 else "NSE"
                    
                    data = {
                        "symbol": sym,
                        "exchange": exch,
                        "ltp": quote.ltp,
                        "open": quote.open,
                        "high": quote.high,
                        "low": quote.low,
                        "prev_close": quote.prev_close,
                        "volume": quote.volume,
                        "change": round(change, 2),
                        "change_percent": round(change_percent, 2)
                    }
                    
                    result[key] = data
                    
                    # Cache it
                    # Extract symbol/exchange from key if possible or match with input
                    # Key from broker is "SYMBOL:EXCHANGE"
                    await quote_cache.set(key, data, ttl=5)
                    
            except Exception as e:
                logger.error(f"Batch quote fetch error: {e}")
        
        return result
    
    async def get_ltp_batch(self, symbols: List[Dict[str, str]]) -> Dict[str, float]:
        """
        Get LTP for multiple symbols.
        
        Args:
            symbols: List of {symbol, exchange} dicts
        
        Returns:
            Dict mapping "symbol:exchange" to LTP
        """
        return await self.broker.get_ltp(symbols)
    
    async def _get_from_db(
        self,
        symbol: str,
        exchange: str,
        interval: str,
        from_dt: datetime,
        to_dt: datetime
    ) -> List[OHLCCandle]:
        """Get candles from database"""
        result = await self.db.execute(
            select(OHLCHistory).where(
                and_(
                    OHLCHistory.symbol == symbol,
                    OHLCHistory.exchange == exchange,
                    OHLCHistory.interval == interval,
                    OHLCHistory.timestamp >= from_dt,
                    OHLCHistory.timestamp <= to_dt
                )
            ).order_by(OHLCHistory.timestamp)
        )
        
        rows = result.scalars().all()
        
        return [
            OHLCCandle(
                timestamp=int(row.timestamp.timestamp()),
                open=row.open,
                high=row.high,
                low=row.low,
                close=row.close,
                volume=row.volume
            )
            for row in rows
        ]
    
    async def _store_candles(
        self,
        symbol: str,
        exchange: str,
        interval: str,
        candles: List[OHLCCandle]
    ) -> None:
        """
        Store candles in database with bulk upsert logic.
        
        OPTIMIZED: Uses bulk insert with ON CONFLICT for much faster writes.
        """
        if not candles:
            return
        
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert
        from sqlalchemy import text
        
        try:
            # Prepare data for bulk insert
            values = []
            for candle in candles:
                timestamp = datetime.fromtimestamp(candle.timestamp)
                values.append({
                    "symbol": symbol,
                    "exchange": exchange,
                    "interval": interval,
                    "timestamp": timestamp,
                    "open": candle.open,
                    "high": candle.high,
                    "low": candle.low,
                    "close": candle.close,
                    "volume": candle.volume
                })
            
            # Use SQLite's INSERT OR REPLACE for bulk upsert
            # This is much faster than individual SELECT + INSERT/UPDATE
            for batch_start in range(0, len(values), 100):
                batch = values[batch_start:batch_start + 100]
                
                stmt = sqlite_insert(OHLCHistory).values(batch)
                stmt = stmt.on_conflict_do_update(
                    index_elements=['symbol', 'exchange', 'interval', 'timestamp'],
                    set_={
                        'open': stmt.excluded.open,
                        'high': stmt.excluded.high,
                        'low': stmt.excluded.low,
                        'close': stmt.excluded.close,
                        'volume': stmt.excluded.volume
                    }
                )
                await self.db.execute(stmt)
            
            await self.db.commit()
            logger.debug(f"Stored {len(candles)} candles for {symbol}:{exchange}:{interval}")
            
        except Exception as e:
            logger.warning(f"Bulk insert failed, falling back to individual inserts: {e}")
            # Fallback to individual inserts if bulk fails
            for candle in candles:
                timestamp = datetime.fromtimestamp(candle.timestamp)
                
                existing = await self.db.execute(
                    select(OHLCHistory).where(
                        and_(
                            OHLCHistory.symbol == symbol,
                            OHLCHistory.exchange == exchange,
                            OHLCHistory.interval == interval,
                            OHLCHistory.timestamp == timestamp
                        )
                    )
                )
                
                row = existing.scalar_one_or_none()
                
                if row:
                    row.open = candle.open
                    row.high = candle.high
                    row.low = candle.low
                    row.close = candle.close
                    row.volume = candle.volume
                else:
                    new_row = OHLCHistory(
                        symbol=symbol,
                        exchange=exchange,
                        interval=interval,
                        timestamp=timestamp,
                        open=candle.open,
                        high=candle.high,
                        low=candle.low,
                        close=candle.close,
                        volume=candle.volume
                    )
                    self.db.add(new_row)
            
            await self.db.commit()
    
    def _find_missing_ranges(
        self,
        candles: List[OHLCCandle],
        from_dt: datetime,
        to_dt: datetime,
        interval: str
    ) -> List[Tuple[datetime, datetime]]:
        """
        Find date ranges with missing data.
        
        Returns list of (start, end) tuples for missing ranges.
        """
        if not candles:
            return [(from_dt, to_dt)]
        
        # Get interval duration
        interval_minutes = self._get_interval_minutes(interval)
        
        # For daily/weekly/monthly, just check if we have recent data
        if interval in ["1d", "1w", "1M", "ONE_DAY", "ONE_WEEK", "ONE_MONTH"]:
            last_candle_time = datetime.fromtimestamp(candles[-1].timestamp)
            
            # If last candle is more than 1 day old, fetch new data
            if (to_dt - last_candle_time).days > 1:
                return [(last_candle_time + timedelta(days=1), to_dt)]
            return []
        
        # For intraday, check for gaps
        missing = []
        
        # Check start
        first_candle_time = datetime.fromtimestamp(candles[0].timestamp)
        if (first_candle_time - from_dt).total_seconds() > interval_minutes * 60 * 2:
            missing.append((from_dt, first_candle_time - timedelta(minutes=interval_minutes)))
        
        # Check end
        last_candle_time = datetime.fromtimestamp(candles[-1].timestamp)
        if (to_dt - last_candle_time).total_seconds() > interval_minutes * 60 * 2:
            missing.append((last_candle_time + timedelta(minutes=interval_minutes), to_dt))
        
        return missing
    
    def _get_interval_minutes(self, interval: str) -> int:
        """Get interval duration in minutes"""
        mapping = {
            "1m": 1, "ONE_MINUTE": 1,
            "3m": 3, "THREE_MINUTE": 3,
            "5m": 5, "FIVE_MINUTE": 5,
            "10m": 10, "TEN_MINUTE": 10,
            "15m": 15, "FIFTEEN_MINUTE": 15,
            "30m": 30, "THIRTY_MINUTE": 30,
            "1h": 60, "ONE_HOUR": 60,
            "2h": 120, "TWO_HOUR": 120,
            "4h": 240, "FOUR_HOUR": 240,
            "1d": 1440, "ONE_DAY": 1440,
            "1w": 10080, "ONE_WEEK": 10080,
            "1M": 43200, "ONE_MONTH": 43200,
        }
        return mapping.get(interval, 1)
    
    def _deduplicate_candles(self, candles: List[OHLCCandle]) -> List[OHLCCandle]:
        """Remove duplicate candles, keeping last occurrence"""
        seen = {}
        for candle in candles:
            seen[candle.timestamp] = candle
        return list(seen.values())


def calculate_change(ltp: float, prev_close: float) -> Tuple[float, float]:
    """
    Calculate price change and percentage.
    
    Args:
        ltp: Last traded price
        prev_close: Previous close price
    
    Returns:
        Tuple of (change, change_percent)
    """
    if prev_close <= 0:
        return 0.0, 0.0
    
    change = ltp - prev_close
    change_percent = (change / prev_close) * 100
    
    return round(change, 2), round(change_percent, 2)


def convert_timestamp_to_ist(timestamp: int) -> int:
    """Add IST offset to UTC timestamp"""
    return timestamp + IST_OFFSET_SECONDS


def convert_timestamp_from_ist(timestamp: int) -> int:
    """Remove IST offset from timestamp"""
    return timestamp - IST_OFFSET_SECONDS
