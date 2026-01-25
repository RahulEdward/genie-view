"""
Angel One SmartAPI Adapter
REST API implementation for Angel One broker
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
import httpx
import asyncio

from app.brokers.base import (
    BrokerAdapter, OHLCCandle, Quote, SymbolInfo,
    AuthResult, WebSocketConfig
)
from app.brokers.angelone.endpoints import (
    BASE_URL, WEBSOCKET_URL, ENDPOINTS, INTERVAL_MAP,
    EXCHANGE_MAP, SUPPORTED_EXCHANGES, ERROR_CODE_MAP,
    DEFAULT_HEADERS, INDEX_SYMBOLS, NSE_EQUITY_TOKENS
)
from app.brokers.angelone.transformers import (
    transform_candle_data, transform_quote_data,
    transform_symbol_info, parse_angel_error,
    normalize_expiry
)
from app.api.exceptions import (
    AuthenticationError, BrokerError, SymbolNotFoundError
)
from app.utils.logger import logger


class AngelOneAdapter(BrokerAdapter):
    """Angel One SmartAPI REST implementation"""
    
    broker_name = "angelone"
    supported_exchanges = SUPPORTED_EXCHANGES
    interval_map = INTERVAL_MAP
    
    def __init__(self, api_key: str):
        """
        Initialize Angel One adapter.
        
        Args:
            api_key: Angel One API key
        """
        self.api_key = api_key
        self.jwt_token: Optional[str] = None
        self.refresh_token_value: Optional[str] = None
        self.feed_token: Optional[str] = None
        self.client_id: Optional[str] = None
        
        # Cache for various data
        self._symbol_cache: Dict[str, str] = {}
        self._search_cache: Dict[str, List[SymbolInfo]] = {}
        self._search_cache_expiry: Dict[str, datetime] = {}
    
    def _get_headers(self, include_auth: bool = True) -> Dict[str, str]:
        """Generate request headers"""
        headers = DEFAULT_HEADERS.copy()
        headers["X-PrivateKey"] = self.api_key
        
        if include_auth and self.jwt_token:
            headers["Authorization"] = f"Bearer {self.jwt_token}"
        
        return headers
    
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        include_auth: bool = True
    ) -> Dict:
        """Make HTTP request to Angel One API"""
        url = f"{BASE_URL}{endpoint}"
        headers = self._get_headers(include_auth)
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                if method.upper() == "GET":
                    response = await client.get(url, headers=headers)
                else:
                    response = await client.post(url, json=data, headers=headers)
                
                response.raise_for_status()
                return response.json()
                
            except httpx.HTTPStatusError as e:
                error_text = e.response.text
                logger.error(f"HTTP error: {e.response.status_code} - {error_text}")
                try:
                    error_data = e.response.json() if error_text else {}
                except:
                    error_data = {"message": error_text}
                raise BrokerError(
                    message=error_data.get("message", str(e)),
                    details={"status_code": e.response.status_code, "response": error_text}
                )
            except httpx.RequestError as e:
                logger.error(f"Request error: {e}")
                raise BrokerError(message=f"Connection error: {str(e)}")
    
    async def authenticate(self, credentials: Dict[str, str]) -> AuthResult:
        """
        Authenticate with Angel One using TOTP.
        
        Args:
            credentials: {client_id, password, totp}
        """
        payload = {
            "clientcode": credentials["client_id"],
            "password": credentials["password"],
            "totp": credentials["totp"]
        }
        
        try:
            response = await self._make_request(
                "POST",
                ENDPOINTS["login"],
                data=payload,
                include_auth=False
            )
            
            if response.get("status") and response.get("data"):
                data = response["data"]
                self.jwt_token = data.get("jwtToken")
                self.refresh_token_value = data.get("refreshToken")
                self.feed_token = data.get("feedToken")
                self.client_id = credentials["client_id"]
                
                logger.info(f"Angel One login successful for {self.client_id}")
                
                return AuthResult(
                    success=True,
                    jwt_token=self.jwt_token,
                    refresh_token=self.refresh_token_value,
                    feed_token=self.feed_token,
                    client_id=self.client_id
                )
            
            # Parse error
            error_code, error_msg = parse_angel_error(response)
            logger.warning(f"Angel One login failed: {error_code} - {error_msg}")
            
            return AuthResult(
                success=False,
                error_code=error_code,
                error_message=error_msg
            )
            
        except BrokerError as e:
            return AuthResult(
                success=False,
                error_code="BROKER_ERROR",
                error_message=str(e)
            )
    
    async def refresh_token(self, refresh_token: str) -> AuthResult:
        """Refresh expired JWT token"""
        payload = {
            "refreshToken": refresh_token
        }
        
        try:
            response = await self._make_request(
                "POST",
                ENDPOINTS["refresh_token"],
                data=payload,
                include_auth=False
            )
            
            if response.get("status") and response.get("data"):
                data = response["data"]
                self.jwt_token = data.get("jwtToken")
                self.refresh_token_value = data.get("refreshToken")
                self.feed_token = data.get("feedToken")
                
                logger.info("Angel One token refreshed successfully")
                
                return AuthResult(
                    success=True,
                    jwt_token=self.jwt_token,
                    refresh_token=self.refresh_token_value,
                    feed_token=self.feed_token,
                    client_id=self.client_id
                )
            
            error_code, error_msg = parse_angel_error(response)
            return AuthResult(
                success=False,
                error_code=error_code,
                error_message=error_msg
            )
            
        except BrokerError as e:
            return AuthResult(
                success=False,
                error_code="BROKER_ERROR",
                error_message=str(e)
            )
    
    async def logout(self, client_id: str) -> bool:
        """Logout and invalidate session"""
        try:
            payload = {"clientcode": client_id}
            response = await self._make_request(
                "POST",
                ENDPOINTS["logout"],
                data=payload
            )
            
            self.jwt_token = None
            self.refresh_token_value = None
            self.feed_token = None
            
            return response.get("status", False)
            
        except Exception as e:
            logger.error(f"Logout error: {e}")
            return False
    
    async def get_historical_data(
        self,
        symbol: str,
        exchange: str,
        interval: str,
        from_date: datetime,
        to_date: datetime,
        symbol_token: Optional[str] = None
    ) -> List[OHLCCandle]:
        """Fetch historical OHLC candle data"""
        self.validate_exchange(exchange)
        
        # Get symbol token if not provided
        if not symbol_token:
            symbol_token = await self.get_symbol_token(symbol, exchange)
            if not symbol_token:
                raise SymbolNotFoundError(symbol)
        
        # Ensure to_date is not in the future
        now = datetime.now()
        if to_date > now:
            to_date = now
        
        # Angel One API expects specific time format
        # For daily candles, use 09:15 as start time and 15:30 as end time
        converted_interval = self.convert_interval(interval)
        
        if converted_interval in ["ONE_DAY", "ONE_WEEK", "ONE_MONTH"]:
            from_str = from_date.strftime("%Y-%m-%d 09:15")
            to_str = to_date.strftime("%Y-%m-%d 15:30")
        else:
            from_str = from_date.strftime("%Y-%m-%d %H:%M")
            to_str = to_date.strftime("%Y-%m-%d %H:%M")
        
        payload = {
            "exchange": EXCHANGE_MAP.get(exchange, exchange),
            "symboltoken": symbol_token,
            "interval": converted_interval,
            "fromdate": from_str,
            "todate": to_str
        }
        
        logger.info(f"Fetching history for {symbol}: {payload}")
        
        response = await self._make_request(
            "POST",
            ENDPOINTS["candle"],
            data=payload
        )
        
        if response.get("status") and response.get("data"):
            return transform_candle_data(response["data"])
        
        logger.warning(f"No data returned for {symbol}: {response}")
        return []
    
    async def get_quote(self, symbol: str, exchange: str) -> Quote:
        """Get current quote for a symbol"""
        self.validate_exchange(exchange)
        
        symbol_token = await self.get_symbol_token(symbol, exchange)
        if not symbol_token:
            raise SymbolNotFoundError(symbol)
        
        payload = {
            "mode": "FULL",
            "exchangeTokens": {
                EXCHANGE_MAP.get(exchange, exchange): [symbol_token]
            }
        }
        
        response = await self._make_request(
            "POST",
            ENDPOINTS["quote"],
            data=payload
        )
        
        if response.get("status") and response.get("data"):
            return transform_quote_data(
                response["data"],
                symbol,
                exchange
            )
        
        raise BrokerError(message="Failed to get quote")
    
    async def get_ltp(self, symbols: List[Dict[str, str]]) -> Dict[str, float]:
        """Get LTP for multiple symbols"""
        # Group by exchange
        exchange_tokens: Dict[str, List[str]] = {}
        symbol_map: Dict[str, str] = {}  # token -> symbol:exchange
        
        for item in symbols:
            symbol = item["symbol"]
            exchange = item.get("exchange", "NSE")
            
            # Use provided token if available, otherwise look it up
            token = item.get("token")
            if not token:
                token = await self.get_symbol_token(symbol, exchange)
            
            if token:
                ex = EXCHANGE_MAP.get(exchange, exchange)
                if ex not in exchange_tokens:
                    exchange_tokens[ex] = []
                exchange_tokens[ex].append(token)
                symbol_map[token] = f"{symbol}:{exchange}"
        
        if not exchange_tokens:
            return {}
        
        payload = {
            "mode": "LTP",
            "exchangeTokens": exchange_tokens
        }
        
        response = await self._make_request(
            "POST",
            ENDPOINTS["quote"],
            data=payload
        )
        
        result = {}
        if response.get("status") and response.get("data"):
            fetched = response["data"].get("fetched", [])
            for item in fetched:
                token = item.get("symbolToken")
                if token in symbol_map:
                    result[symbol_map[token]] = float(item.get("ltp", 0))
        
        return result
    
    async def get_quotes_batch(self, symbols: List[Dict[str, str]]) -> Dict[str, Quote]:
        """Get full quotes for multiple symbols"""
        # Group by exchange
        exchange_tokens: Dict[str, List[str]] = {}
        symbol_map: Dict[str, str] = {}  # token -> symbol:exchange
        
        for item in symbols:
            symbol = item["symbol"]
            exchange = item.get("exchange", "NSE")
            
            # Use provided token if available, otherwise look it up
            token = item.get("token")
            if not token:
                token = await self.get_symbol_token(symbol, exchange)
            
            if token:
                ex = EXCHANGE_MAP.get(exchange, exchange)
                if ex not in exchange_tokens:
                    exchange_tokens[ex] = []
                exchange_tokens[ex].append(token)
                symbol_map[token] = f"{symbol}:{exchange}"
            else:
                 logger.warning(f"Token not found for {symbol} on {exchange}")
        
        if not exchange_tokens:
            logger.warning("No tokens found for batch quote request")
            return {}
        
        payload = {
            "mode": "FULL",
            "exchangeTokens": exchange_tokens
        }
        
        logger.debug(f"Batch quote payload: {payload}")
        
        try:
            response = await self._make_request(
                "POST",
                ENDPOINTS["quote"],
                data=payload
            )
        except Exception as e:
            logger.error(f"Batch quote API error: {e}")
            return {}
        
        result = {}
        if response.get("status") and response.get("data"):
            fetched = response["data"].get("fetched", [])
            logger.debug(f"Batch quote fetched count: {len(fetched)}")
            
            for item in fetched:
                token = item.get("symbolToken")
                if token in symbol_map:
                    key = symbol_map[token]
                    symbol_part = key.split(":")[0]  # Extract symbol name
                    exchange_part = key.split(":")[1] # Extract exchange
                    
                    # Use transformer for consistent Quote object
                    try:
                        quote = transform_quote_data(item, symbol_part, exchange_part)
                        result[key] = quote
                    except Exception as e:
                        logger.warning(f"Error acting quote for {key}: {e}")
        else:
             logger.warning(f"Batch quote response invalid: {response}")
        
        return result
    
    async def get_option_chain(
        self,
        underlying: str,
        exchange: str,
        expiry: Optional[str] = None,
        db: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Get option chain for an underlying.
        
        NEW IMPLEMENTATION: Uses database queries instead of search API calls.
        This eliminates rate limit errors by reducing API calls from 100+ to 2-3.
        
        Args:
            underlying: Underlying symbol (NIFTY, BANKNIFTY, etc.)
            exchange: Exchange code (NFO, BFO)
            expiry: Optional expiry date
            db: Database session (required for querying instruments)
        
        Returns:
            Option chain data with calls and puts
        """
        # Get underlying LTP
        underlying_quote = None
        try:
            if underlying in INDEX_SYMBOLS:
                idx_info = INDEX_SYMBOLS[underlying]
                underlying_quote = await self.get_quote(underlying, idx_info["exchange"])
            else:
                underlying_quote = await self.get_quote(underlying, "NSE")
        except Exception as e:
            logger.warning(f"Could not get underlying quote: {e}")
        
        spot_price = underlying_quote.ltp if underlying_quote else 0
        
        # If no database session provided, return empty chain
        if not db:
            logger.error("Database session required for option chain query")
            return {
                "spot_price": spot_price,
                "expiry": expiry,
                "options": [],
                "calls": [],
                "puts": []
            }
        
        # Normalize expiry
        normalized_expiry = normalize_expiry(expiry) if expiry else None
        
        if not normalized_expiry:
            logger.warning(f"No expiry provided for {underlying} option chain")
            return {
                "spot_price": spot_price,
                "expiry": expiry,
                "options": [],
                "calls": [],
                "puts": []
            }
        
        # Query instruments from database (NO API CALLS!)
        from app.models.database import InstrumentMaster
        from sqlalchemy import select
        
        try:
            logger.info(f"Querying database for {underlying} options with expiry {normalized_expiry}")
            
            result = await db.execute(
                select(InstrumentMaster).where(
                    InstrumentMaster.name == underlying.upper(),
                    InstrumentMaster.exchange == exchange.upper(),
                    InstrumentMaster.expiry == normalized_expiry,
                    InstrumentMaster.option_type.in_(["CE", "PE"])
                ).order_by(InstrumentMaster.strike.asc())
            )
            
            instruments = result.scalars().all()
            
            if not instruments:
                logger.warning(f"No options found in database for {underlying} {normalized_expiry} on {exchange}")
                return {
                    "spot_price": spot_price,
                    "expiry": expiry,
                    "options": [],
                    "calls": [],
                    "puts": []
                }
            
            logger.info(f"Found {len(instruments)} options in database")
            
            # Fetch prices for options in batches (ONLY API CALLS NEEDED)
            quotes_map = {}
            batch_size = 50
            
            for i in range(0, len(instruments), batch_size):
                batch = instruments[i:i + batch_size]
                # Pass tokens directly from database to avoid search API calls
                batch_symbols = [
                    {
                        "symbol": inst.symbol,
                        "exchange": exchange,
                        "token": inst.token
                    }
                    for inst in batch
                ]
                
                try:
                    batch_quotes = await self.get_quotes_batch(batch_symbols)
                    quotes_map.update(batch_quotes)
                    logger.debug(f"Fetched quotes for batch {i//batch_size + 1}: {len(batch_quotes)} quotes")
                except Exception as e:
                    logger.warning(f"Error fetching option batch {i}: {e}")
                
                # Small delay between batches
                if i + batch_size < len(instruments):
                    await asyncio.sleep(0.2)
            
            # Build chain response
            calls = []
            puts = []
            
            for inst in instruments:
                key = f"{inst.symbol}:{exchange}"
                quote = quotes_map.get(key)
                
                opt_data = {
                    "symbol": inst.symbol,
                    "strike": inst.strike,
                    "token": inst.token,
                    "ltp": quote.ltp if quote else 0,
                    "prev_close": quote.prev_close if quote else 0,
                    "open": quote.open if quote else 0,
                    "high": quote.high if quote else 0,
                    "low": quote.low if quote else 0,
                    "oi": quote.oi if quote else 0,
                    "volume": quote.volume if quote else 0,
                    "bid": quote.bid if quote else 0,
                    "ask": quote.ask if quote else 0,
                    "lot_size": inst.lot_size,
                    "expiry": inst.expiry,
                    "option_type": inst.option_type
                }
                
                if inst.option_type == "CE":
                    calls.append(opt_data)
                else:
                    puts.append(opt_data)
            
            # Sort by strike
            calls.sort(key=lambda x: x["strike"])
            puts.sort(key=lambda x: x["strike"])
            
            logger.info(f"Option chain: {len(calls)} calls, {len(puts)} puts, spot={spot_price}")
            
            return {
                "spot_price": spot_price,
                "expiry": expiry,
                "options": calls + puts,
                "calls": calls,
                "puts": puts
            }
            
        except Exception as e:
            logger.error(f"Error querying option chain from database: {e}")
            return {
                "spot_price": spot_price,
                "expiry": expiry,
                "options": [],
                "calls": [],
                "puts": []
            }
    
    async def get_expiry_dates(
        self,
        underlying: str,
        exchange: str,
        instrument_type: str = "options"
    ) -> List[str]:
        """Get available expiry dates"""
        # Search for symbols and extract unique expiries
        try:
            # Search for symbols
            # We search for just the underlying to get all related instruments
            options = await self.search_symbols(underlying, exchange)
            
            expiries = set()
            for opt in options:
                # Filter by instrument type if specified
                if instrument_type == "options":
                    if opt.instrument_type not in ["OPTIDX", "OPTSTK"]:
                        continue
                elif instrument_type == "futures":
                     if opt.instrument_type not in ["FUTIDX", "FUTSTK"]:
                        continue
                        
                if opt.expiry:
                    # Normalize to ensure uniqueness
                    norm_exp = normalize_expiry(opt.expiry)
                    if norm_exp:
                        expiries.add(norm_exp)
            
            # Sort by date using OptionService's sorter or custom sort
            # Since we return strings, we'll relying on caller or basic sort
            # But standard string sort YYYY-MM-DD is best, but here we have DDMMMYY
            # Let's rely on basic sort for now, or better: parse and sort
            
            sorted_expiries = sorted(list(expiries), key=lambda x: datetime.strptime(x, "%d%b%y") if len(x) == 7 else x)
            return sorted_expiries
            
        except Exception as e:
            logger.warning(f"Error getting expiry dates: {e}")
            return []
    
    async def search_symbols(
        self,
        query: str,
        exchange: Optional[str] = None
    ) -> List[SymbolInfo]:
        """Search for symbols"""
        # Angel One requires exchange to be specified
        # If not provided, default to NSE for equity, NFO for derivatives
        if not exchange:
            exchange = "NSE"
        
        # Check cache
        mapped_exchange = EXCHANGE_MAP.get(exchange, exchange)
        cache_key = f"{query}:{mapped_exchange}"
        now = datetime.now()
        if cache_key in self._search_cache:
            expiry = self._search_cache_expiry.get(cache_key)
            if expiry and expiry > now:
                # logger.debug(f"Search cache hit for '{query}' on {exchange}")
                return self._search_cache[cache_key]
        
        payload = {
            "exchange": mapped_exchange,
            "searchscrip": query
        }
        
        try:
            response = await self._make_request(
                "POST",
                ENDPOINTS["search"],
                data=payload
            )
            
            if response.get("status") and response.get("data"):
                data = response["data"]
                # logger.debug(f"Raw search data for '{query}': {data[:2]}")
                return [
                    transform_symbol_info(item)
                    for item in data
                ]
            
            logger.debug(f"Search API returned no data for query '{query}': {response}")
            return []
        except BrokerError as e:
            # Log but don't raise - return empty list
            logger.warning(f"Search API error for '{query}' on {exchange}: {e}")
            return []
    
    async def get_symbol_token(
        self,
        symbol: str,
        exchange: str
    ) -> Optional[str]:
        """Get symbol token for a trading symbol"""
        # Normalize inputs
        symbol = symbol.strip().upper()
        exchange = exchange.strip().upper()
        
        cache_key = f"{symbol}:{exchange}"
        
        # Check cache
        if cache_key in self._symbol_cache:
            return self._symbol_cache[cache_key]
        
        # Check index symbols
        # Map NSE_INDEX to NSE for checking if needed, but INDEX_SYMBOLS has specific keys
        if symbol in INDEX_SYMBOLS:
            idx_info = INDEX_SYMBOLS[symbol]
            # Check if exchange matches or is mapped
            req_ex = EXCHANGE_MAP.get(exchange, exchange)
            idx_ex = EXCHANGE_MAP.get(idx_info["exchange"], idx_info["exchange"])
            
            if req_ex == idx_ex:
                token = idx_info["token"]
                self._symbol_cache[cache_key] = token
                return token
        
        # Check NSE equity tokens (fallback for common stocks)
        # Verify exchange is NSE
        mapped_exchange = EXCHANGE_MAP.get(exchange, exchange)
        if mapped_exchange == "NSE" and symbol in NSE_EQUITY_TOKENS:
            token = NSE_EQUITY_TOKENS[symbol]
            self._symbol_cache[cache_key] = token
            # logger.debug(f"Using cached token for {symbol}: {token}")
            return token
        
        # Search for symbol via API
        try:
            logger.debug(f"Searching API for token: {symbol}:{exchange}")
            results = await self.search_symbols(symbol, exchange)
            
            for item in results:
                # Exact match
                if item.symbol == symbol:
                    self._symbol_cache[cache_key] = item.token
                    return item.token
                
                # EQ match
                if item.symbol == f"{symbol}-EQ":
                    self._symbol_cache[cache_key] = item.token
                    return item.token
            
            logger.warning(f"Token not found for {symbol} on {exchange}")
            return None
            
        except Exception as e:
            logger.error(f"Error getting token for {symbol}: {e}")
            return None
    
    async def get_instrument_master(self) -> List[SymbolInfo]:
        """Download full instrument master list"""
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(ENDPOINTS["instrument_master"])
            response.raise_for_status()
            data = response.json()
        
        return [transform_symbol_info(item) for item in data]
    
    def get_websocket_config(self) -> WebSocketConfig:
        """Get WebSocket connection configuration"""
        return WebSocketConfig(
            url=WEBSOCKET_URL,
            auth_token=self.jwt_token or "",
            feed_token=self.feed_token or "",
            client_id=self.client_id or ""
        )
    
    def set_tokens(
        self,
        jwt_token: str,
        refresh_token: str,
        feed_token: str,
        client_id: str
    ):
        """Set authentication tokens (for restoring session)"""
        self.jwt_token = jwt_token
        self.refresh_token_value = refresh_token
        self.feed_token = feed_token
        self.client_id = client_id
    
    async def get_positions(self) -> List[Dict[str, Any]]:
        """Get open positions"""
        try:
            response = await self._make_request("GET", ENDPOINTS["positions"])
            
            if response.get("status") and response.get("data"):
                positions = []
                for pos in response["data"]:
                    positions.append({
                        "symbol": pos.get("tradingsymbol", ""),
                        "exchange": pos.get("exchange", ""),
                        "product": pos.get("producttype", ""),
                        "quantity": int(pos.get("netqty", 0)),
                        "average_price": float(pos.get("netprice", 0)),
                        "ltp": float(pos.get("ltp", 0)),
                        "pnl": float(pos.get("pnl", 0)),
                        "timestamp": pos.get("updatetime", "")
                    })
                return positions
            
            return []
        except Exception as e:
            logger.error(f"Error fetching positions: {e}")
            return []
    
    async def get_orders(self) -> List[Dict[str, Any]]:
        """Get order book"""
        try:
            response = await self._make_request("GET", ENDPOINTS["orders"])
            
            if response.get("status") and response.get("data"):
                orders = []
                for order in response["data"]:
                    orders.append({
                        "orderid": order.get("orderid", ""),
                        "symbol": order.get("tradingsymbol", ""),
                        "exchange": order.get("exchange", ""),
                        "action": order.get("transactiontype", ""),
                        "quantity": int(order.get("quantity", 0)),
                        "price": float(order.get("price", 0)),
                        "pricetype": order.get("ordertype", ""),
                        "product": order.get("producttype", ""),
                        "order_status": order.get("orderstatus", ""),
                        "timestamp": order.get("updatetime", "")
                    })
                return orders
            
            return []
        except Exception as e:
            logger.error(f"Error fetching orders: {e}")
            return []
    
    async def get_funds(self) -> Dict[str, Any]:
        """Get account funds/margin"""
        try:
            response = await self._make_request("GET", ENDPOINTS["funds"])
            
            if response.get("status") and response.get("data"):
                data = response["data"]
                return {
                    "availablecash": data.get("availablecash", "0"),
                    "utiliseddebits": data.get("utiliseddebits", "0"),
                    "collateral": data.get("collateral", "0"),
                    "m2mrealized": data.get("m2mrealized", "0"),
                    "m2munrealized": data.get("m2munrealized", "0")
                }
            
            return {}
        except Exception as e:
            logger.error(f"Error fetching funds: {e}")
            return {}
    
    async def get_holdings(self) -> List[Dict[str, Any]]:
        """Get holdings"""
        try:
            response = await self._make_request("GET", ENDPOINTS["holdings"])
            
            if response.get("status") and response.get("data"):
                holdings = []
                for holding in response["data"]:
                    holdings.append({
                        "symbol": holding.get("tradingsymbol", ""),
                        "exchange": holding.get("exchange", ""),
                        "quantity": int(holding.get("quantity", 0)),
                        "pnl": float(holding.get("pnl", 0)),
                        "pnlpercent": float(holding.get("pnlpercentage", 0)),
                        "timestamp": ""
                    })
                return holdings
            
            return []
        except Exception as e:
            logger.error(f"Error fetching holdings: {e}")
            return []
    
    async def get_trades(self) -> List[Dict[str, Any]]:
        """Get trade book"""
        try:
            response = await self._make_request("GET", ENDPOINTS["tradebook"])
            
            if response.get("status") and response.get("data"):
                trades = []
                for trade in response["data"]:
                    trades.append({
                        "orderid": trade.get("orderid", ""),
                        "symbol": trade.get("tradingsymbol", ""),
                        "exchange": trade.get("exchange", ""),
                        "action": trade.get("transactiontype", ""),
                        "quantity": int(trade.get("quantity", 0)),
                        "average_price": float(trade.get("price", 0)),
                        "trade_value": float(trade.get("fillprice", 0)) * int(trade.get("quantity", 0)),
                        "timestamp": trade.get("filltime", "")
                    })
                return trades
            
            return []
        except Exception as e:
            logger.error(f"Error fetching trades: {e}")
            return []

    async def place_order(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Place order"""
        try:
            symbol = params.get("symbol")
            exchange = params.get("exchange", "NSE")
            
            # Lookup token
            token = await self.get_symbol_token(symbol, exchange)
            if not token:
                raise ValueError(f"Token not found for {symbol}")
            
            # Map order type and variety
            price_type = params.get("pricetype", "MARKET").upper()
            variety = "NORMAL"
            angel_order_type = "MARKET"
            
            if price_type == "MARKET":
                angel_order_type = "MARKET"
            elif price_type == "LIMIT":
                angel_order_type = "LIMIT"
            elif price_type == "SL":
                angel_order_type = "STOPLOSS_LIMIT"
                variety = "STOPLOSS"
            elif price_type == "SL-M":
                angel_order_type = "STOPLOSS_MARKET"
                variety = "STOPLOSS"
                
            trigger_price = params.get("trigger_price", 0)
            
            payload = {
                "variety": variety,
                "tradingsymbol": symbol,
                "symboltoken": token,
                "transactiontype": params.get("action", "").upper(),
                "exchange": exchange,
                "ordertype": angel_order_type,
                "producttype": params.get("product", "MIS").upper(),
                "duration": "DAY",
                "price": str(params.get("price", 0)),
                "quantity": str(params.get("quantity", 1)),
                "triggerprice": str(trigger_price) if trigger_price else "0"
            }
            
            # Send request
            response = await self._make_request("POST", ENDPOINTS["placeOrder"], json=payload)
            return response

        except Exception as e:
            logger.error(f"Error placing order: {e}")
            return {"status": False, "message": str(e)}

    async def modify_order(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Modify order"""
        try:
            symbol = params.get("symbol")
            exchange = params.get("exchange", "NSE")
            token = await self.get_symbol_token(symbol, exchange)
             
            payload = {
                "variety": "NORMAL", # Assumption, modification usually mostly NORMAL/STOPLOSS
                "orderid": params.get("orderid"),
                "ordertype": params.get("pricetype", "LIMIT").upper(),
                "producttype": params.get("product", "MIS").upper(),
                "duration": "DAY",
                "price": str(params.get("price", 0)),
                "quantity": str(params.get("quantity", 1)),
                "tradingsymbol": symbol,
                "symboltoken": token,
                "exchange": exchange
            }
            
            # Try to detect variety/trigger price modification if needed?
            # For simplicity assuming basic modification
            if params.get("trigger_price"):
                 payload["triggerprice"] = str(params.get("trigger_price"))
                 payload["variety"] = "STOPLOSS" # Assumption

            response = await self._make_request("POST", ENDPOINTS["modifyOrder"], json=payload)
            return response
        except Exception as e:
            logger.error(f"Error modifying order: {e}")
            return {"status": False, "message": str(e)}

    async def cancel_order(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Cancel order"""
        try:
            payload = {
                "variety": params.get("variety", "NORMAL"),
                "orderid": params.get("orderid")
            }
            response = await self._make_request("POST", ENDPOINTS["cancelOrder"], json=payload)
            return response
        except Exception as e:
            logger.error(f"Error cancelling order: {e}")
            return {"status": False, "message": str(e)}
