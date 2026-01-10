"""
Angel One SmartAPI Adapter
REST API implementation for Angel One broker
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
import httpx

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
    transform_symbol_info, parse_angel_error
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
        
        # Symbol token cache
        self._symbol_cache: Dict[str, str] = {}
    
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
                logger.error(f"HTTP error: {e.response.status_code} - {e.response.text}")
                error_data = e.response.json() if e.response.text else {}
                raise BrokerError(
                    message=error_data.get("message", str(e)),
                    details={"status_code": e.response.status_code}
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
        
        payload = {
            "exchange": EXCHANGE_MAP.get(exchange, exchange),
            "symboltoken": symbol_token,
            "interval": self.convert_interval(interval),
            "fromdate": from_date.strftime("%Y-%m-%d %H:%M"),
            "todate": to_date.strftime("%Y-%m-%d %H:%M")
        }
        
        logger.debug(f"Fetching history: {payload}")
        
        response = await self._make_request(
            "POST",
            ENDPOINTS["candle"],
            data=payload
        )
        
        if response.get("status") and response.get("data"):
            return transform_candle_data(response["data"])
        
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
    
    async def get_option_chain(
        self,
        underlying: str,
        exchange: str,
        expiry: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get option chain for an underlying"""
        # Angel One doesn't have a direct option chain API
        # We need to search for options and build the chain
        
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
        
        underlying_ltp = underlying_quote.ltp if underlying_quote else 0
        
        # Search for option symbols
        search_query = f"{underlying}"
        if expiry:
            search_query = f"{underlying}{expiry}"
        
        options = await self.search_symbols(search_query, exchange)
        
        # Filter and organize by strike
        chain: Dict[float, Dict] = {}
        
        for opt in options:
            if opt.strike and opt.option_type:
                strike = opt.strike
                if strike not in chain:
                    chain[strike] = {"strike": strike, "ce": None, "pe": None}
                
                opt_type = "ce" if opt.option_type == "CE" else "pe"
                chain[strike][opt_type] = {
                    "symbol": opt.symbol,
                    "token": opt.token,
                    "ltp": 0,  # Will be filled by quote
                    "oi": 0,
                    "volume": 0,
                    "bid": 0,
                    "ask": 0,
                    "lot_size": opt.lot_size
                }
        
        # Calculate ATM strike
        strikes = sorted(chain.keys())
        atm_strike = min(strikes, key=lambda x: abs(x - underlying_ltp)) if strikes else 0
        
        return {
            "underlying": underlying,
            "underlyingLTP": underlying_ltp,
            "atmStrike": atm_strike,
            "expiry": expiry,
            "chain": list(chain.values())
        }
    
    async def get_expiry_dates(
        self,
        underlying: str,
        exchange: str,
        instrument_type: str = "options"
    ) -> List[str]:
        """Get available expiry dates"""
        # Search for symbols and extract unique expiries
        options = await self.search_symbols(underlying, exchange)
        
        expiries = set()
        for opt in options:
            if opt.expiry:
                expiries.add(opt.expiry)
        
        # Sort by date
        return sorted(list(expiries))
    
    async def search_symbols(
        self,
        query: str,
        exchange: Optional[str] = None
    ) -> List[SymbolInfo]:
        """Search for symbols"""
        payload = {
            "exchange": EXCHANGE_MAP.get(exchange, exchange) if exchange else "",
            "searchscrip": query
        }
        
        response = await self._make_request(
            "POST",
            ENDPOINTS["search"],
            data=payload
        )
        
        if response.get("status") and response.get("data"):
            return [
                transform_symbol_info(item)
                for item in response["data"]
            ]
        
        return []
    
    async def get_symbol_token(
        self,
        symbol: str,
        exchange: str
    ) -> Optional[str]:
        """Get symbol token for a trading symbol"""
        cache_key = f"{symbol}:{exchange}"
        
        # Check cache
        if cache_key in self._symbol_cache:
            return self._symbol_cache[cache_key]
        
        # Check index symbols
        if symbol in INDEX_SYMBOLS:
            token = INDEX_SYMBOLS[symbol]["token"]
            self._symbol_cache[cache_key] = token
            return token
        
        # Check NSE equity tokens (fallback for common stocks)
        if exchange == "NSE" and symbol in NSE_EQUITY_TOKENS:
            token = NSE_EQUITY_TOKENS[symbol]
            self._symbol_cache[cache_key] = token
            logger.debug(f"Using cached token for {symbol}: {token}")
            return token
        
        # Search for symbol via API
        try:
            results = await self.search_symbols(symbol, exchange)
            
            for item in results:
                if item.symbol == symbol and item.exchange == exchange:
                    self._symbol_cache[cache_key] = item.token
                    return item.token
                
                # Also check for symbol-EQ format (Angel One sometimes uses this)
                if item.symbol == f"{symbol}-EQ" and item.exchange == exchange:
                    self._symbol_cache[cache_key] = item.token
                    return item.token
        except Exception as e:
            logger.warning(f"Symbol search failed for {symbol}: {e}")
        
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
