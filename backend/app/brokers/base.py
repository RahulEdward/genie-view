"""
Broker Adapter Base Class
Abstract interface for all broker integrations
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel


# ==================== Data Models ====================

class OHLCCandle(BaseModel):
    """OHLC candle data"""
    timestamp: int  # Unix timestamp in seconds
    open: float
    high: float
    low: float
    close: float
    volume: int = 0


class Quote(BaseModel):
    """Real-time quote data"""
    symbol: str
    exchange: str
    ltp: float
    open: float
    high: float
    low: float
    prev_close: float
    volume: int
    timestamp: int
    bid: Optional[float] = None
    ask: Optional[float] = None
    bid_qty: Optional[int] = None
    ask_qty: Optional[int] = None


class OptionData(BaseModel):
    """Option contract data"""
    symbol: str
    token: str
    strike: float
    option_type: str  # CE or PE
    expiry: str
    ltp: float
    bid: float
    ask: float
    oi: int
    volume: int
    lot_size: int
    prev_close: Optional[float] = 0
    open: Optional[float] = 0
    high: Optional[float] = 0
    low: Optional[float] = 0


class Greeks(BaseModel):
    """Option Greeks"""
    delta: float
    gamma: float
    theta: float
    vega: float
    iv: float  # Implied Volatility in percentage


class SymbolInfo(BaseModel):
    """Symbol/Instrument information"""
    symbol: str
    token: str
    name: Optional[str] = None
    exchange: str
    instrument_type: Optional[str] = None
    lot_size: int = 1
    tick_size: float = 0.05
    expiry: Optional[str] = None
    strike: Optional[float] = None
    option_type: Optional[str] = None


class AuthResult(BaseModel):
    """Authentication result"""
    success: bool
    jwt_token: Optional[str] = None
    refresh_token: Optional[str] = None
    feed_token: Optional[str] = None
    client_id: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


class WebSocketConfig(BaseModel):
    """WebSocket configuration"""
    url: str
    auth_token: str
    feed_token: str
    client_id: str


# ==================== Broker Adapter Interface ====================

class BrokerAdapter(ABC):
    """
    Abstract base class for broker integrations.
    
    All broker adapters must implement this interface to ensure
    consistent behavior across different brokers.
    """
    
    # Broker identification
    broker_name: str = "base"
    
    # Supported exchanges
    supported_exchanges: List[str] = []
    
    # Interval mapping (internal -> broker format)
    interval_map: Dict[str, str] = {}
    
    @abstractmethod
    async def authenticate(self, credentials: Dict[str, str]) -> AuthResult:
        """
        Authenticate with the broker.
        
        Args:
            credentials: Dict containing broker-specific credentials
                - client_id: Client/User ID
                - password: Password or PIN
                - totp: TOTP code (if required)
                - api_key: API key (if required)
        
        Returns:
            AuthResult with tokens and status
        """
        pass
    
    @abstractmethod
    async def refresh_token(self, refresh_token: str) -> AuthResult:
        """
        Refresh expired JWT token.
        
        Args:
            refresh_token: Refresh token from previous auth
        
        Returns:
            AuthResult with new tokens
        """
        pass
    
    @abstractmethod
    async def logout(self, client_id: str) -> bool:
        """
        Logout and invalidate session.
        
        Args:
            client_id: Client ID to logout
        
        Returns:
            True if logout successful
        """
        pass
    
    @abstractmethod
    async def get_historical_data(
        self,
        symbol: str,
        exchange: str,
        interval: str,
        from_date: datetime,
        to_date: datetime,
        symbol_token: Optional[str] = None
    ) -> List[OHLCCandle]:
        """
        Fetch historical OHLC candle data.
        
        Args:
            symbol: Trading symbol
            exchange: Exchange code (NSE, BSE, NFO, etc.)
            interval: Candle interval (1m, 5m, 15m, 1h, 1d, etc.)
            from_date: Start date
            to_date: End date
            symbol_token: Optional symbol token (for faster lookup)
        
        Returns:
            List of OHLC candles
        """
        pass
    
    @abstractmethod
    async def get_quote(self, symbol: str, exchange: str) -> Quote:
        """
        Get current quote for a symbol.
        
        Args:
            symbol: Trading symbol
            exchange: Exchange code
        
        Returns:
            Quote with LTP, OHLC, volume
        """
        pass
    
    @abstractmethod
    async def get_ltp(self, symbols: List[Dict[str, str]]) -> Dict[str, float]:
        """
        Get LTP for multiple symbols.
        
        Args:
            symbols: List of {symbol, exchange} dicts
        
        Returns:
            Dict mapping "symbol:exchange" to LTP
        """
        pass
    
    @abstractmethod
    async def get_option_chain(
        self,
        underlying: str,
        exchange: str,
        expiry: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get option chain for an underlying.
        
        Args:
            underlying: Underlying symbol (NIFTY, BANKNIFTY, etc.)
            exchange: Exchange code (NFO, BFO)
            expiry: Optional expiry date in DDMMMYY format
        
        Returns:
            Dict with underlying info and chain data
        """
        pass
    
    @abstractmethod
    async def get_expiry_dates(
        self,
        underlying: str,
        exchange: str,
        instrument_type: str = "options"
    ) -> List[str]:
        """
        Get available expiry dates for an underlying.
        
        Args:
            underlying: Underlying symbol
            exchange: Exchange code
            instrument_type: "options" or "futures"
        
        Returns:
            List of expiry dates in DDMMMYY format
        """
        pass
    
    @abstractmethod
    async def search_symbols(
        self,
        query: str,
        exchange: Optional[str] = None
    ) -> List[SymbolInfo]:
        """
        Search for symbols.
        
        Args:
            query: Search query
            exchange: Optional exchange filter
        
        Returns:
            List of matching symbols
        """
        pass
    
    @abstractmethod
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
            Symbol token or None if not found
        """
        pass
    
    @abstractmethod
    async def get_instrument_master(self) -> List[SymbolInfo]:
        """
        Download full instrument master list.
        
        Returns:
            List of all instruments
        """
        pass
    
    @abstractmethod
    def get_websocket_config(self) -> WebSocketConfig:
        """
        Get WebSocket connection configuration.
        
        Returns:
            WebSocketConfig with URL and auth details
        """
        pass
    
    # ==================== Helper Methods ====================
    
    def set_tokens(
        self,
        jwt_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
        feed_token: Optional[str] = None,
        client_id: Optional[str] = None
    ) -> None:
        """
        Set authentication tokens on the adapter.
        
        Args:
            jwt_token: JWT access token
            refresh_token: Refresh token
            feed_token: WebSocket feed token
            client_id: Client ID
        """
        if jwt_token:
            self._jwt_token = jwt_token
        if refresh_token:
            self._refresh_token = refresh_token
        if feed_token:
            self._feed_token = feed_token
        if client_id:
            self._client_id = client_id
    
    def convert_interval(self, interval: str) -> str:
        """Convert internal interval to broker format"""
        return self.interval_map.get(interval, interval)
    
    def is_exchange_supported(self, exchange: str) -> bool:
        """Check if exchange is supported"""
        return exchange in self.supported_exchanges
    
    def validate_exchange(self, exchange: str) -> None:
        """Validate exchange and raise error if not supported"""
        if not self.is_exchange_supported(exchange):
            from app.api.exceptions import ValidationError
            raise ValidationError(
                f"Exchange '{exchange}' not supported. "
                f"Supported: {', '.join(self.supported_exchanges)}"
            )
