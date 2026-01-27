"""
Symbol Service
Handles symbol search, instrument master, and symbol lookup
"""

from typing import List, Dict, Optional
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, func, delete
import httpx
import asyncio

from app.brokers.base import BrokerAdapter, SymbolInfo
from app.models.database import InstrumentMaster
from app.utils.cache import symbol_cache
from app.utils.logger import logger
from app.config import settings
from app.api.exceptions import BrokerError


class SymbolService:
    """Service for symbol search and instrument master operations"""
    
    def __init__(self, broker: BrokerAdapter, db: AsyncSession):
        self.broker = broker
        self.db = db
    
    async def download_instrument_master(self) -> List[Dict]:
        """
        Download instrument master file from Angel One.
        
        Implements retry logic with exponential backoff (3 attempts: 1s, 2s, 4s).
        
        Returns:
            List of instrument dictionaries
        
        Raises:
            BrokerError: If download fails after all retries
        """
        from app.brokers.angelone.endpoints import ENDPOINTS
        
        url = ENDPOINTS["instrument_master"]
        max_retries = 3
        retry_delays = [1, 2, 4]  # Exponential backoff in seconds
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Downloading instrument master (attempt {attempt + 1}/{max_retries})...")
                
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.get(url)
                    response.raise_for_status()
                    
                    # Parse JSON
                    data = response.json()
                    
                    if not isinstance(data, list):
                        raise ValueError("Instrument master file is not a JSON array")
                    
                    logger.info(f"Successfully downloaded {len(data)} instruments")
                    return data
                    
            except httpx.HTTPStatusError as e:
                error_msg = f"HTTP error {e.response.status_code}: {e.response.text[:200]}"
                logger.error(f"Download attempt {attempt + 1} failed: {error_msg}")
                
                if attempt < max_retries - 1:
                    delay = retry_delays[attempt]
                    logger.info(f"Retrying in {delay} seconds...")
                    await asyncio.sleep(delay)
                else:
                    raise BrokerError(
                        message=f"Failed to download instrument master after {max_retries} retries",
                        details={"url": url, "last_error": error_msg, "retry_count": max_retries}
                    )
                    
            except httpx.RequestError as e:
                error_msg = f"Connection error: {str(e)}"
                logger.error(f"Download attempt {attempt + 1} failed: {error_msg}")
                
                if attempt < max_retries - 1:
                    delay = retry_delays[attempt]
                    logger.info(f"Retrying in {delay} seconds...")
                    await asyncio.sleep(delay)
                else:
                    raise BrokerError(
                        message=f"Failed to download instrument master after {max_retries} retries",
                        details={"url": url, "last_error": error_msg, "retry_count": max_retries}
                    )
                    
            except (ValueError, KeyError) as e:
                error_msg = f"Parse error: {str(e)}"
                logger.error(f"Download attempt {attempt + 1} failed: {error_msg}")
                
                if attempt < max_retries - 1:
                    delay = retry_delays[attempt]
                    logger.info(f"Retrying in {delay} seconds...")
                    await asyncio.sleep(delay)
                else:
                    raise BrokerError(
                        message=f"Failed to parse instrument master after {max_retries} retries",
                        details={"url": url, "last_error": error_msg, "retry_count": max_retries}
                    )
        
        # Should never reach here, but just in case
        raise BrokerError(
            message="Failed to download instrument master",
            details={"url": url, "retry_count": max_retries}
        )
    
    def parse_instrument_record(self, record: Dict) -> Optional[InstrumentMaster]:
        """
        Parse a single instrument record from the master file.
        
        Validates required fields and extracts option_type from symbol.
        Applies transformations similar to OpenAlgo's master_contract_db.py
        
        Args:
            record: Raw instrument dictionary from JSON
        
        Returns:
            InstrumentMaster model instance or None if invalid
        """
        try:
            # Validate required fields
            required_fields = ["token", "symbol", "exch_seg"]
            for field in required_fields:
                if field not in record or not record[field]:
                    logger.debug(f"Skipping record: missing required field '{field}'")
                    return None
            
            # Extract fields
            token = str(record["token"]).strip()
            symbol = str(record["symbol"]).strip().upper()
            name = str(record.get("name", "")).strip().upper() or symbol
            exchange = str(record["exch_seg"]).strip().upper()
            instrument_type = str(record.get("instrumenttype", "")).strip().upper()
            
            # Normalize name for common indices
            name_mapping = {
                "NIFTY 50": "NIFTY",
                "NIFTY NEXT 50": "NIFTYNXT50",
                "NIFTY FIN SERVICE": "FINNIFTY",
                "NIFTY BANK": "BANKNIFTY",
                "NIFTY MID SELECT": "MIDCPNIFTY",
                "INDIA VIX": "INDIAVIX",
                "SNSX50": "SENSEX50",
            }
            name = name_mapping.get(name, name)
            
            # Parse numeric fields with defaults
            try:
                lot_size = int(record.get("lotsize", 1))
            except (ValueError, TypeError):
                lot_size = 1
            
            # Tick size is stored multiplied by 100 in Angel One
            try:
                raw_tick = float(record.get("tick_size", 5))
                tick_size = raw_tick / 100  # Convert to actual tick size
            except (ValueError, TypeError):
                tick_size = 0.05
            
            # Parse expiry and convert format (19MAR2024 -> 19MAR2024, keep as is for DB)
            expiry = None
            if record.get("expiry"):
                expiry = str(record["expiry"]).strip().upper()
            
            # Parse strike (optional)
            # Angel One stores strikes multiplied by 100 (e.g., 2365000 for 23650)
            # We divide by 100 to get the actual strike price
            strike = None
            if record.get("strike"):
                try:
                    raw_strike = float(record["strike"])
                    strike = raw_strike / 100  # Convert to actual strike price
                    
                    # Special handling for CDS options (currency) - divide by additional 1000
                    if instrument_type in ["OPTCUR", "OPTIRC"] and exchange == "CDS":
                        strike = strike / 1000
                except (ValueError, TypeError):
                    pass
            
            # Extract option_type from symbol (CE/PE at the end)
            option_type = None
            if symbol.endswith("CE"):
                option_type = "CE"
            elif symbol.endswith("PE"):
                option_type = "PE"
            
            # Normalize instrument_type for options to CE/PE
            if instrument_type in ["OPTIDX", "OPTSTK", "OPTFUT", "OPTCUR", "OPTIRC"]:
                if option_type:
                    instrument_type = option_type
            
            # Normalize futures instrument types to FUT
            if instrument_type in ["FUTIDX", "FUTSTK", "FUTCOM", "FUTCUR", "FUTIRC", "FUTIRT"]:
                instrument_type = "FUT"
            
            # Create InstrumentMaster instance
            return InstrumentMaster(
                symbol=symbol,
                token=token,
                name=name,
                exchange=exchange,
                instrument_type=instrument_type,
                lot_size=lot_size,
                tick_size=tick_size,
                expiry=expiry,
                strike=strike,
                option_type=option_type,
                updated_at=datetime.utcnow()
            )
            
        except Exception as e:
            logger.warning(f"Error parsing instrument record: {e}, record: {record}")
            return None
    
    async def store_instruments_bulk(self, instruments: List[InstrumentMaster]) -> int:
        """
        Store instruments in database using bulk insert.
        
        Clears existing data and uses bulk insert for performance.
        Wraps in transaction for atomicity.
        Deduplicates instruments by (symbol, exchange) before inserting.
        
        Args:
            instruments: List of InstrumentMaster instances
        
        Returns:
            Number of instruments stored
        """
        if not instruments:
            logger.warning("No instruments to store")
            return 0
        
        try:
            # Clear existing instrument_master table
            logger.info("Clearing existing instrument master data...")
            await self.db.execute(delete(InstrumentMaster))
            
            # Deduplicate instruments by (symbol, exchange)
            # Keep the first occurrence of each unique (symbol, exchange) pair
            seen = set()
            unique_instruments = []
            duplicates = 0
            
            for inst in instruments:
                key = (inst.symbol, inst.exchange)
                if key not in seen:
                    seen.add(key)
                    unique_instruments.append(inst)
                else:
                    duplicates += 1
            
            if duplicates > 0:
                logger.info(f"Removed {duplicates} duplicate instruments")
            
            # Prepare bulk insert data
            instrument_dicts = []
            for inst in unique_instruments:
                instrument_dicts.append({
                    "symbol": inst.symbol,
                    "token": inst.token,
                    "name": inst.name,
                    "exchange": inst.exchange,
                    "instrument_type": inst.instrument_type,
                    "lot_size": inst.lot_size,
                    "tick_size": inst.tick_size,
                    "expiry": inst.expiry,
                    "strike": inst.strike,
                    "option_type": inst.option_type,
                    "updated_at": inst.updated_at
                })
            
            # Bulk insert using SQLAlchemy bulk_insert_mappings
            logger.info(f"Bulk inserting {len(instrument_dicts)} instruments...")
            await self.db.run_sync(
                lambda session: session.bulk_insert_mappings(InstrumentMaster, instrument_dicts)
            )
            
            # Commit transaction
            await self.db.commit()
            
            logger.info(f"Successfully stored {len(instrument_dicts)} instruments")
            return len(instrument_dicts)
            
        except Exception as e:
            logger.error(f"Error storing instruments: {e}")
            await self.db.rollback()
            raise
    
    async def query_options_by_expiry(
        self,
        underlying: str,
        exchange: str,
        expiry: str
    ) -> List[InstrumentMaster]:
        """
        Query option instruments for a specific underlying and expiry.
        
        Uses indexed query for performance.
        
        Args:
            underlying: Underlying symbol (e.g., "NIFTY")
            exchange: Exchange code (e.g., "NFO")
            expiry: Expiry date in normalized format (e.g., "30JAN25")
        
        Returns:
            List of matching option instruments sorted by strike
        """
        try:
            # Normalize inputs
            underlying = underlying.strip().upper()
            exchange = exchange.strip().upper()
            expiry = expiry.strip().upper()
            
            # Query using composite index
            result = await self.db.execute(
                select(InstrumentMaster).where(
                    InstrumentMaster.name == underlying,
                    InstrumentMaster.exchange == exchange,
                    InstrumentMaster.expiry == expiry,
                    InstrumentMaster.option_type.in_(["CE", "PE"])
                ).order_by(InstrumentMaster.strike.asc())
            )
            
            instruments = result.scalars().all()
            
            logger.debug(f"Found {len(instruments)} options for {underlying} {expiry} on {exchange}")
            return list(instruments)
            
        except Exception as e:
            logger.error(f"Error querying options: {e}")
            return []
    
    async def get_instrument_health(self) -> Dict:
        """
        Check health status of instrument master data.
        
        Returns:
            {
                "available": bool,
                "count": int,
                "last_updated": datetime,
                "is_stale": bool
            }
        """
        try:
            # Get count of instruments
            result = await self.db.execute(
                select(func.count(InstrumentMaster.id))
            )
            count = result.scalar() or 0
            
            # Get last updated timestamp
            result = await self.db.execute(
                select(func.max(InstrumentMaster.updated_at))
            )
            last_updated = result.scalar()
            
            # Check if data is stale (>48 hours old)
            is_stale = False
            if last_updated:
                age = datetime.utcnow() - last_updated
                is_stale = age > timedelta(hours=48)
            
            available = count > 0
            
            return {
                "available": available,
                "count": count,
                "last_updated": last_updated,
                "is_stale": is_stale
            }
            
        except Exception as e:
            logger.error(f"Error checking instrument health: {e}")
            return {
                "available": False,
                "count": 0,
                "last_updated": None,
                "is_stale": True
            }
    
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
        
        Uses download_instrument_master() instead of broker.get_instrument_master().
        Implements retry logic with exponential backoff.
        Clears existing data before bulk insert.
        Uses transactions for atomic updates.
        
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
        
        try:
            # Download instrument master file
            raw_instruments = await self.download_instrument_master()
            
            if not raw_instruments:
                logger.warning("No instruments received from download")
                return 0
            
            # Parse instruments
            parsed_instruments = []
            failed_count = 0
            
            for record in raw_instruments:
                inst = self.parse_instrument_record(record)
                if inst:
                    parsed_instruments.append(inst)
                else:
                    failed_count += 1
            
            logger.info(f"Parsed {len(parsed_instruments)} instruments ({failed_count} failed)")
            
            if not parsed_instruments:
                logger.warning("No valid instruments after parsing")
                return 0
            
            # Store in database using bulk insert
            count = await self.store_instruments_bulk(parsed_instruments)
            
            # Update refresh timestamp
            await self._set_last_refresh_time()
            
            logger.info(f"Instrument master refreshed: {count} instruments")
            return count
            
        except BrokerError as e:
            logger.error(f"Failed to refresh instrument master: {e}")
            # Don't raise - allow application to continue with existing data
            return 0
        except Exception as e:
            logger.error(f"Unexpected error refreshing instrument master: {e}")
            return 0
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
