"""
Pydantic Schemas
Request/Response models for API
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ==================== Base Response Models ====================

class BaseResponse(BaseModel):
    """Base response model"""
    status: str = "success"


class ErrorResponse(BaseModel):
    """Standard error response"""
    status: str = "error"
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None


class SuccessResponse(BaseResponse):
    """Success response with data"""
    data: Any


# ==================== Error Codes ====================

class ErrorCodes:
    """Standard error codes"""
    AUTH_FAILED = "AUTH_FAILED"
    INVALID_TOKEN = "INVALID_TOKEN"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    RATE_LIMITED = "RATE_LIMITED"
    BROKER_ERROR = "BROKER_ERROR"
    SYMBOL_NOT_FOUND = "SYMBOL_NOT_FOUND"
    INVALID_INTERVAL = "INVALID_INTERVAL"
    INVALID_EXCHANGE = "INVALID_EXCHANGE"
    NO_DATA = "NO_DATA"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    NOT_FOUND = "NOT_FOUND"


ERROR_MESSAGES = {
    ErrorCodes.AUTH_FAILED: "Authentication failed",
    ErrorCodes.INVALID_TOKEN: "Invalid or expired token",
    ErrorCodes.TOKEN_EXPIRED: "Session token has expired",
    ErrorCodes.RATE_LIMITED: "Rate limit exceeded. Please try again later",
    ErrorCodes.BROKER_ERROR: "Broker API error",
    ErrorCodes.SYMBOL_NOT_FOUND: "Symbol not found",
    ErrorCodes.INVALID_INTERVAL: "Invalid interval specified",
    ErrorCodes.INVALID_EXCHANGE: "Invalid exchange specified",
    ErrorCodes.NO_DATA: "No data available for the requested parameters",
    ErrorCodes.VALIDATION_ERROR: "Request validation failed",
    ErrorCodes.INTERNAL_ERROR: "Internal server error",
    ErrorCodes.NOT_FOUND: "Resource not found",
}


# ==================== Auth Schemas ====================

class LoginRequest(BaseModel):
    """Login request"""
    broker: str = Field(default="angelone", description="Broker name")
    client_id: str = Field(..., description="Client ID")
    password: str = Field(..., description="Password or PIN")
    totp: str = Field(..., description="TOTP code")
    api_key: Optional[str] = Field(None, description="Broker API key")
    totp_secret: Optional[str] = Field(None, description="TOTP secret for auto-generation")
    save_credentials: bool = Field(default=False, description="Save credentials to DB")


class LoginResponse(BaseResponse):
    """Login response"""
    data: Dict[str, str]  # Contains apikey


class SavedCredentialsResponse(BaseResponse):
    """Saved credentials response (without sensitive data)"""
    data: List[Dict[str, str]]  # List of {broker, client_id}


# ==================== Market Data Schemas ====================

class HistoryRequest(BaseModel):
    """Historical data request"""
    apikey: str
    symbol: str
    exchange: str = "NSE"
    interval: str = "1d"
    start_date: str  # YYYY-MM-DD
    end_date: str  # YYYY-MM-DD


class OHLCCandle(BaseModel):
    """OHLC candle data"""
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: int = 0


class HistoryResponse(BaseResponse):
    """Historical data response"""
    data: List[OHLCCandle]


class QuoteRequest(BaseModel):
    """Quote request"""
    apikey: str
    symbol: str
    exchange: str = "NSE"


class QuoteData(BaseModel):
    """Quote data"""
    ltp: float
    open: float
    high: float
    low: float
    prev_close: float
    volume: int
    change: Optional[float] = None
    change_percent: Optional[float] = None


class QuoteResponse(BaseResponse):
    """Quote response"""
    data: QuoteData


# ==================== Option Chain Schemas ====================

class OptionChainRequest(BaseModel):
    """Option chain request"""
    apikey: str
    underlying: str
    exchange: str = "NFO"
    expiry: Optional[str] = None
    strike_count: int = 15


class OptionLeg(BaseModel):
    """Single option leg data"""
    symbol: str
    ltp: float
    prev_close: Optional[float] = 0
    open: Optional[float] = 0
    high: Optional[float] = 0
    low: Optional[float] = 0
    bid: float
    ask: float
    oi: int
    volume: int
    lot_size: Optional[int] = 0
    label: Optional[str] = None  # ITM, ATM, OTM


class OptionStrike(BaseModel):
    """Option strike with CE and PE"""
    strike: float
    ce: Optional[OptionLeg] = None
    pe: Optional[OptionLeg] = None


class OptionChainData(BaseModel):
    """Option chain data"""
    underlying: str
    underlyingLTP: float
    underlyingPrevClose: Optional[float] = 0
    atmStrike: float
    expiryDate: str
    chain: List[OptionStrike]


class OptionChainResponse(BaseResponse):
    """Option chain response"""
    data: OptionChainData


# ==================== Greeks Schemas ====================

class GreeksRequest(BaseModel):
    """Greeks request"""
    apikey: str
    symbol: str
    exchange: str = "NFO"


class GreeksBatchRequest(BaseModel):
    """Batch Greeks request"""
    apikey: str
    symbols: List[Dict[str, str]]  # [{"symbol": "...", "exchange": "..."}]
    interest_rate: Optional[float] = 0.1


class GreeksData(BaseModel):
    """Greeks data"""
    delta: float
    gamma: float
    theta: float
    vega: float
    iv: float


class GreeksResponse(BaseResponse):
    """Greeks response"""
    data: GreeksData


# ==================== Expiry Schemas ====================

class ExpiryRequest(BaseModel):
    """Expiry dates request"""
    apikey: str
    underlying: Optional[str] = None  # Backend field name
    symbol: Optional[str] = None  # Frontend field name (alias)
    exchange: str = "NFO"
    instrumenttype: str = "options"
    
    @property
    def get_underlying(self) -> str:
        """Get underlying symbol from either field"""
        return self.underlying or self.symbol or ""


class ExpiryResponse(BaseResponse):
    """Expiry dates response"""
    data: List[str]


# ==================== Search Schemas ====================

class SearchRequest(BaseModel):
    """Symbol search request"""
    apikey: str
    query: str
    exchange: Optional[str] = None


class SymbolInfo(BaseModel):
    """Symbol information"""
    symbol: str
    name: Optional[str] = None
    exchange: str
    token: str
    instrument_type: Optional[str] = None
    lot_size: int = 1
    tick_size: float = 0.05


class SearchResponse(BaseResponse):
    """Search response"""
    data: List[SymbolInfo]


# ==================== Market Timing Schemas ====================

class MarketTimingsRequest(BaseModel):
    """Market timings request"""
    apikey: str
    date: str  # YYYY-MM-DD


class ExchangeTiming(BaseModel):
    """Exchange timing"""
    exchange: str
    start_time: int  # epoch milliseconds
    end_time: int


class MarketTimingsResponse(BaseResponse):
    """Market timings response"""
    data: List[ExchangeTiming]


class MarketHolidaysRequest(BaseModel):
    """Market holidays request"""
    apikey: str
    year: int


class HolidayInfo(BaseModel):
    """Holiday information"""
    date: str
    description: str
    holiday_type: str
    closed_exchanges: List[str]


class MarketHolidaysResponse(BaseResponse):
    """Market holidays response"""
    data: List[HolidayInfo]
