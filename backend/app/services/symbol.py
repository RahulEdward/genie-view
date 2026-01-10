"""
Symbol Service
Handles symbol search, instrument master, and symbol lookup
"""

from typing import List, Dict, Optional
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, func

from app.brokers.base import BrokerAdapter, SymbolInfo
from app.models.database import InstrumentMaster
from app.utils.cache import symbol_cache
from app.utils.logger import logger
from app.config import settings


class SymbolService:
    """Service for symbol search and instrument master operations"""
    
    def __init__(self, broker: BrokerAdapter, db: AsyncSession):
        self.broker = broker
        self.db = db
    
    async def search(
        self,
        query: str,
        exchange: Optional[str] = None,
        instrument_type: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict]:
        """
        Search for symbols with fuzzy matching.
        
        Args:
            query: Search query (symbol name or trading symbol)
            exchange: Optional exchange filter
            instrument_type: Optional instrument type filter (EQ, FUT, OPT)
            limit: Maximum results to return
        
        Returns:
            List of matching symbols with required fields
        """
        if not query or len(query) < 2:
            return []
        
        cache_key = f"search:{query}:{exchange}:{instrument_type}:{limit}"
        
        # Check cache
        cached = await symbol_cache.get(cache_key)
        if cached:
            return cached
        
        # Search in database first
        results = await self._search_db(query, exchange, instrument_type, limit)
        
        # If no results in DB, try broker API
        if not results:
            broker_results = await self.broker.search_symbols(query, exchange)
            results = [self._symbol_to_dict(s) for s in broker_results[:limit]]
        
        # Cache for 5 minutes
        if results:
            await symbol_cache.set(cache_key, results, ttl=300)
        
        return results
    
    async def get_symbol_token(
        self,
        symbol: str,
        exchange: str
    ) -> Optional[str]:
        """
        Get symbol token for a trading symbol.
        
        Args:
            symbol: Trading symbol
            exchange: Exchange code
        
        Returns:
            Symbol token or None
        """
        cache_key = f"token:{symbol}:{exchange}"
        
        # Check cache
        cached = await symbol_cache.get(cache_key)
        if cached:
            return cached
        
        # Check database
        result = await self.db.execute(
            select(InstrumentMaster).where(
                InstrumentMaster.symbol == symbol,
                InstrumentMaster.exchange == exchange
            )
        )
        row = result.scalar_one_or_none()
        
        if row:
            await symbol_cache.set(cache_key, row.token, ttl=3600)
            return row.token
        
        # Try broker API
        token = await self.broker.get_symbol_token(symbol, exchange)
        
        if token:
            await symbol_cache.set(cache_key, token, ttl=3600)
        
        return token
    
    async def refresh_master(self, force: bool = False) -> int:
        """
        Refresh instrument master from broker.
        
        Args:
            force: Force refresh even if recently updated
        
        Returns:
            Number of instruments updated
        """
        # Check last refresh time
        if not force:
            last_refresh = await self._get_last_refresh_time()
            if last_refresh and (datetime.utcnow() - last_refresh) < timedelta(hours=12):
                logger.info("Instrument master recently refreshed, skipping")
                return 0
        
        logger.info("Refreshing instrument master...")
        
        # Fetch from broker
        instruments = await self.broker.get_instrument_master()
        
        if not instruments:
            logger.warning("No instruments received from broker")
            return 0
        
        # Update database
        count = 0
        for inst in instruments:
            await self._upsert_instrument(inst)
            count += 1
            
            # Commit in batches
            if count % 1000 == 0:
                await self.db.commit()
                logger.debug(f"Processed {count} instruments")
        
        await self.db.commit()
        
        # Update refresh timestamp
        await self._set_last_refresh_time()
        
        logger.info(f"Instrument master refreshed: {count} instruments")
        
        return count
    
    async def get_instrument(
        self,
        symbol: str,
        exchange: str
    ) -> Optional[Dict]:
        """
        Get full instrument details.
        
        Args:
            symbol: Trading symbol
            exchange: Exchange code
        
        Returns:
            Instrument details dict or None
        """
        result = await self.db.execute(
            select(InstrumentMaster).where(
                InstrumentMaster.symbol == symbol,
                InstrumentMaster.exchange == exchange
            )
        )
        row = result.scalar_one_or_none()
        
        if row:
            return {
                "symbol": row.symbol,
                "token": row.token,
                "name": row.name,
                "exchange": row.exchange,
                "instrument_type": row.instrument_type,
                "lot_size": row.lot_size,
                "tick_size": row.tick_size,
                "expiry": row.expiry,
                "strike": row.strike,
                "option_type": row.option_type
            }
        
        return None
    
    async def _search_db(
        self,
        query: str,
        exchange: Optional[str],
        instrument_type: Optional[str],
        limit: int
    ) -> List[Dict]:
        """Search instruments in database"""
        query_upper = query.upper()
        
        # Build query
        stmt = select(InstrumentMaster).where(
            or_(
                InstrumentMaster.symbol.ilike(f"%{query_upper}%"),
                InstrumentMaster.name.ilike(f"%{query_upper}%")
            )
        )
        
        if exchange:
            stmt = stmt.where(InstrumentMaster.exchange == exchange.upper())
        
        if instrument_type:
            stmt = stmt.where(InstrumentMaster.instrument_type == instrument_type.upper())
        
        # Order by relevance (exact match first, then starts with, then contains)
        stmt = stmt.order_by(
            # Exact match gets priority
            (InstrumentMaster.symbol == query_upper).desc(),
            # Starts with gets second priority
            InstrumentMaster.symbol.startswith(query_upper).desc(),
            # Then alphabetical
            InstrumentMaster.symbol
        ).limit(limit)
        
        result = await self.db.execute(stmt)
        rows = result.scalars().all()
        
        return [
            {
                "symbol": row.symbol,
                "token": row.token,
                "name": row.name,
                "exchange": row.exchange,
                "instrument_type": row.instrument_type,
                "lot_size": row.lot_size,
                "tick_size": row.tick_size,
                "expiry": row.expiry,
                "strike": row.strike,
                "option_type": row.option_type
            }
            for row in rows
        ]
    
    async def _upsert_instrument(self, inst: SymbolInfo) -> None:
        """Insert or update instrument in database"""
        result = await self.db.execute(
            select(InstrumentMaster).where(
                InstrumentMaster.symbol == inst.symbol,
                InstrumentMaster.exchange == inst.exchange
            )
        )
        row = result.scalar_one_or_none()
        
        if row:
            # Update existing
            row.token = inst.token
            row.name = inst.name
            row.instrument_type = inst.instrument_type
            row.lot_size = inst.lot_size
            row.tick_size = inst.tick_size
            row.expiry = inst.expiry
            row.strike = inst.strike
            row.option_type = inst.option_type
            row.updated_at = datetime.utcnow()
        else:
            # Insert new
            new_row = InstrumentMaster(
                symbol=inst.symbol,
                token=inst.token,
                name=inst.name,
                exchange=inst.exchange,
                instrument_type=inst.instrument_type,
                lot_size=inst.lot_size,
                tick_size=inst.tick_size,
                expiry=inst.expiry,
                strike=inst.strike,
                option_type=inst.option_type
            )
            self.db.add(new_row)
    
    async def _get_last_refresh_time(self) -> Optional[datetime]:
        """Get last instrument master refresh time"""
        result = await self.db.execute(
            select(func.max(InstrumentMaster.updated_at))
        )
        return result.scalar()
    
    async def _set_last_refresh_time(self) -> None:
        """Update refresh timestamp in cache"""
        await symbol_cache.set("master_refresh_time", datetime.utcnow().isoformat(), ttl=86400)
    
    def _symbol_to_dict(self, symbol: SymbolInfo) -> Dict:
        """Convert SymbolInfo to dict"""
        return {
            "symbol": symbol.symbol,
            "token": symbol.token,
            "name": symbol.name,
            "exchange": symbol.exchange,
            "instrument_type": symbol.instrument_type,
            "lot_size": symbol.lot_size,
            "tick_size": symbol.tick_size,
            "expiry": symbol.expiry,
            "strike": symbol.strike,
            "option_type": symbol.option_type
        }


def search_symbols_fuzzy(
    query: str,
    symbols: List[Dict],
    limit: int = 20
) -> List[Dict]:
    """
    Fuzzy search symbols in a list.
    
    Args:
        query: Search query
        symbols: List of symbol dicts
        limit: Maximum results
    
    Returns:
        Matching symbols sorted by relevance
    """
    query_upper = query.upper()
    
    results = []
    for sym in symbols:
        symbol = sym.get("symbol", "").upper()
        name = sym.get("name", "").upper()
        
        # Calculate relevance score
        score = 0
        
        if symbol == query_upper:
            score = 100  # Exact match
        elif symbol.startswith(query_upper):
            score = 80  # Starts with
        elif query_upper in symbol:
            score = 60  # Contains in symbol
        elif query_upper in name:
            score = 40  # Contains in name
        else:
            continue
        
        results.append((score, sym))
    
    # Sort by score descending
    results.sort(key=lambda x: x[0], reverse=True)
    
    return [r[1] for r in results[:limit]]
