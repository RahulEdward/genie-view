# Design Document: Modular Trading Backend

## Overview

Yeh document ek modular FastAPI backend ka technical design describe karta hai jo Angel One broker se market data fetch karega. Architecture ko is tarah design kiya gaya hai ki future mein easily naye brokers add ho sakein. Backend OpenAlgo-compatible API format expose karega taaki existing frontend app minimal changes ke saath kaam kar sake.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (React)                          │
│                   (Existing OpenAlgo Client)                     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     FastAPI Backend                              │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    API Layer                             │   │
│  │  /api/v1/history  /api/v1/quotes  /api/v1/optionchain   │   │
│  │  /api/v1/market   /api/v1/search  /api/v1/greeks        │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                  Service Layer                           │   │
│  │  MarketDataService  OptionService  AuthService          │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │               Broker Adapter Layer                       │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │   │
│  │  │ AngelOne    │  │ Zerodha     │  │ Future      │     │   │
│  │  │ Adapter     │  │ Adapter     │  │ Brokers     │     │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘     │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                  WebSocket Manager                       │   │
│  │         (Real-time streaming to clients)                 │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     PostgreSQL Database                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │ Sessions │  │ OHLC     │  │ Symbols  │  │ Cache    │       │
│  │          │  │ History  │  │ Master   │  │          │       │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘       │
└─────────────────────────────────────────────────────────────────┘
```

## Components and Interfaces

### 1. Broker Adapter Interface (Abstract Base Class)

```python
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from datetime import datetime
from pydantic import BaseModel

class OHLCCandle(BaseModel):
    timestamp: int  # Unix timestamp in seconds
    open: float
    high: float
    low: float
    close: float
    volume: int

class Quote(BaseModel):
    symbol: str
    exchange: str
    ltp: float
    open: float
    high: float
    low: float
    prev_close: float
    volume: int
    timestamp: int

class OptionData(BaseModel):
    symbol: str
    strike: float
    option_type: str  # CE or PE
    ltp: float
    bid: float
    ask: float
    oi: int
    volume: int
    lot_size: int

class Greeks(BaseModel):
    delta: float
    gamma: float
    theta: float
    vega: float
    iv: float

class BrokerAdapter(ABC):
    """Abstract interface for broker integrations"""
    
    @abstractmethod
    async def authenticate(self, credentials: Dict) -> Dict:
        """Login and get session tokens"""
        pass
    
    @abstractmethod
    async def refresh_token(self, refresh_token: str) -> Dict:
        """Refresh expired JWT token"""
        pass
    
    @abstractmethod
    async def get_historical_data(
        self, 
        symbol: str, 
        exchange: str, 
        interval: str,
        from_date: datetime,
        to_date: datetime
    ) -> List[OHLCCandle]:
        """Fetch historical OHLC candles"""
        pass
    
    @abstractmethod
    async def get_quote(self, symbol: str, exchange: str) -> Quote:
        """Get current quote for a symbol"""
        pass
    
    @abstractmethod
    async def get_option_chain(
        self, 
        underlying: str, 
        exchange: str,
        expiry: Optional[str] = None
    ) -> Dict:
        """Get option chain data"""
        pass
    
    @abstractmethod
    async def get_expiry_dates(
        self, 
        underlying: str, 
        exchange: str
    ) -> List[str]:
        """Get available expiry dates"""
        pass
    
    @abstractmethod
    async def search_symbols(self, query: str) -> List[Dict]:
        """Search for symbols"""
        pass
    
    @abstractmethod
    async def get_instrument_master(self) -> List[Dict]:
        """Download full instrument master list"""
        pass
    
    @abstractmethod
    def get_websocket_config(self) -> Dict:
        """Get WebSocket connection configuration"""
        pass
```

### 2. Angel One Adapter Implementation

```python
class AngelOneAdapter(BrokerAdapter):
    """Angel One SmartAPI REST implementation"""
    
    BASE_URL = "https://apiconnect.angelone.in"
    
    ENDPOINTS = {
        "login": "/rest/auth/angelbroking/user/v1/loginByPassword",
        "refresh": "/rest/auth/angelbroking/jwt/v1/generateTokens",
        "logout": "/rest/secure/angelbroking/user/v1/logout",
        "profile": "/rest/secure/angelbroking/user/v1/getProfile",
        "candle": "/rest/secure/angelbroking/historical/v1/getCandleData",
        "quote": "/rest/secure/angelbroking/market/v1/quote",
        "ltp": "/rest/secure/angelbroking/order/v1/getLtpData",
        "search": "/rest/secure/angelbroking/order/v1/searchScrip",
    }
    
    INTERVAL_MAP = {
        "1m": "ONE_MINUTE",
        "3m": "THREE_MINUTE",
        "5m": "FIVE_MINUTE",
        "10m": "TEN_MINUTE",
        "15m": "FIFTEEN_MINUTE",
        "30m": "THIRTY_MINUTE",
        "1h": "ONE_HOUR",
        "1d": "ONE_DAY",
        "1w": "ONE_WEEK",
        "1M": "ONE_MONTH"
    }
    
    EXCHANGE_MAP = {
        "NSE": "NSE",
        "BSE": "BSE",
        "NFO": "NFO",
        "BFO": "BFO",
        "MCX": "MCX",
        "CDS": "CDS",
        "NSE_INDEX": "NSE"
    }
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.jwt_token: Optional[str] = None
        self.refresh_token_value: Optional[str] = None
        self.feed_token: Optional[str] = None
        self.client_code: Optional[str] = None
        self.http_client: Optional[httpx.AsyncClient] = None
    
    def _get_headers(self) -> Dict:
        """Generate required headers for Angel One API"""
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-UserType": "USER",
            "X-SourceID": "WEB",
            "X-ClientLocalIP": "127.0.0.1",
            "X-ClientPublicIP": "127.0.0.1",
            "X-MACAddress": "00:00:00:00:00:00",
            "X-PrivateKey": self.api_key,
            "Authorization": f"Bearer {self.jwt_token}" if self.jwt_token else ""
        }
    
    async def authenticate(self, credentials: Dict) -> Dict:
        """
        Login to Angel One using TOTP
        credentials: {client_id, password, totp}
        """
        payload = {
            "clientcode": credentials["client_id"],
            "password": credentials["password"],
            "totp": credentials["totp"]
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}{self.ENDPOINTS['login']}",
                json=payload,
                headers=self._get_headers()
            )
            
        data = response.json()
        if data.get("status") and data.get("data"):
            self.jwt_token = data["data"]["jwtToken"]
            self.refresh_token_value = data["data"]["refreshToken"]
            self.feed_token = data["data"]["feedToken"]
            self.client_code = credentials["client_id"]
            return {
                "status": "success",
                "jwt_token": self.jwt_token,
                "refresh_token": self.refresh_token_value,
                "feed_token": self.feed_token
            }
        
        return {"status": "error", "message": data.get("message", "Login failed")}
    
    async def get_historical_data(
        self,
        symbol: str,
        exchange: str,
        interval: str,
        from_date: datetime,
        to_date: datetime
    ) -> List[OHLCCandle]:
        """Fetch historical candle data from Angel One"""
        # Need symbol token - lookup from master
        symbol_token = await self._get_symbol_token(symbol, exchange)
        
        payload = {
            "exchange": self.EXCHANGE_MAP.get(exchange, exchange),
            "symboltoken": symbol_token,
            "interval": self.INTERVAL_MAP.get(interval, interval),
            "fromdate": from_date.strftime("%Y-%m-%d %H:%M"),
            "todate": to_date.strftime("%Y-%m-%d %H:%M")
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}{self.ENDPOINTS['candle']}",
                json=payload,
                headers=self._get_headers()
            )
        
        data = response.json()
        candles = []
        
        if data.get("status") and data.get("data"):
            for row in data["data"]:
                # Angel One returns: [timestamp, open, high, low, close, volume]
                candles.append(OHLCCandle(
                    timestamp=self._parse_timestamp(row[0]),
                    open=float(row[1]),
                    high=float(row[2]),
                    low=float(row[3]),
                    close=float(row[4]),
                    volume=int(row[5])
                ))
        
        return candles
```

### 3. Market Data Service

```python
class MarketDataService:
    """Service layer for market data operations"""
    
    def __init__(
        self,
        broker: BrokerAdapter,
        db: AsyncSession,
        cache: Redis
    ):
        self.broker = broker
        self.db = db
        self.cache = cache
    
    async def get_history(
        self,
        symbol: str,
        exchange: str,
        interval: str,
        start_date: str,
        end_date: str
    ) -> List[Dict]:
        """
        Get historical data with caching
        1. Check cache for recent data
        2. Check database for stored data
        3. Fetch missing data from broker
        4. Store in database and cache
        """
        cache_key = f"history:{symbol}:{exchange}:{interval}"
        
        # Check cache first
        cached = await self.cache.get(cache_key)
        if cached:
            return json.loads(cached)
        
        # Check database
        from_dt = datetime.strptime(start_date, "%Y-%m-%d")
        to_dt = datetime.strptime(end_date, "%Y-%m-%d")
        
        db_candles = await self._get_from_db(symbol, exchange, interval, from_dt, to_dt)
        
        # Find gaps and fetch from broker
        missing_ranges = self._find_missing_ranges(db_candles, from_dt, to_dt)
        
        for start, end in missing_ranges:
            broker_candles = await self.broker.get_historical_data(
                symbol, exchange, interval, start, end
            )
            await self._store_candles(symbol, exchange, interval, broker_candles)
            db_candles.extend(broker_candles)
        
        # Sort and deduplicate
        db_candles.sort(key=lambda x: x.timestamp)
        result = self._deduplicate(db_candles)
        
        # Cache for 1 minute
        await self.cache.setex(cache_key, 60, json.dumps(result))
        
        return result
    
    async def get_quote(self, symbol: str, exchange: str) -> Dict:
        """Get current quote with change calculation"""
        quote = await self.broker.get_quote(symbol, exchange)
        
        change = quote.ltp - quote.prev_close
        change_percent = (change / quote.prev_close * 100) if quote.prev_close > 0 else 0
        
        return {
            "status": "success",
            "data": {
                "ltp": quote.ltp,
                "open": quote.open,
                "high": quote.high,
                "low": quote.low,
                "prev_close": quote.prev_close,
                "volume": quote.volume,
                "change": round(change, 2),
                "change_percent": round(change_percent, 2)
            }
        }
```

### 4. Option Service

```python
class OptionService:
    """Service for option chain and Greeks"""
    
    def __init__(self, broker: BrokerAdapter, db: AsyncSession):
        self.broker = broker
        self.db = db
    
    async def get_option_chain(
        self,
        underlying: str,
        exchange: str,
        expiry: Optional[str] = None,
        strike_count: int = 15
    ) -> Dict:
        """Get option chain with ATM identification"""
        # Get underlying LTP for ATM calculation
        quote = await self.broker.get_quote(underlying, self._get_index_exchange(exchange))
        underlying_ltp = quote.ltp
        
        # Fetch option chain from broker
        chain_data = await self.broker.get_option_chain(underlying, exchange, expiry)
        
        # Calculate ATM strike
        strikes = [row["strike"] for row in chain_data.get("chain", [])]
        atm_strike = min(strikes, key=lambda x: abs(x - underlying_ltp)) if strikes else 0
        
        # Filter strikes around ATM
        filtered_chain = self._filter_strikes(chain_data["chain"], atm_strike, strike_count)
        
        return {
            "status": "success",
            "data": {
                "underlying": underlying,
                "underlyingLTP": underlying_ltp,
                "atmStrike": atm_strike,
                "expiryDate": chain_data.get("expiry"),
                "chain": filtered_chain
            }
        }
    
    async def calculate_greeks(
        self,
        symbol: str,
        exchange: str,
        spot_price: float,
        strike: float,
        expiry_date: str,
        option_type: str,
        interest_rate: float = 0.1
    ) -> Greeks:
        """Calculate option Greeks using Black-Scholes"""
        from scipy.stats import norm
        import math
        
        # Get option LTP
        quote = await self.broker.get_quote(symbol, exchange)
        option_price = quote.ltp
        
        # Calculate time to expiry in years
        expiry = datetime.strptime(expiry_date, "%d%b%y")
        tte = (expiry - datetime.now()).days / 365.0
        
        if tte <= 0:
            tte = 1/365  # Minimum 1 day
        
        # Calculate IV using Newton-Raphson
        iv = self._calculate_iv(option_price, spot_price, strike, tte, interest_rate, option_type)
        
        # Calculate Greeks
        d1 = (math.log(spot_price / strike) + (interest_rate + iv**2 / 2) * tte) / (iv * math.sqrt(tte))
        d2 = d1 - iv * math.sqrt(tte)
        
        if option_type == "CE":
            delta = norm.cdf(d1)
            theta = (-spot_price * norm.pdf(d1) * iv / (2 * math.sqrt(tte)) 
                    - interest_rate * strike * math.exp(-interest_rate * tte) * norm.cdf(d2)) / 365
        else:
            delta = norm.cdf(d1) - 1
            theta = (-spot_price * norm.pdf(d1) * iv / (2 * math.sqrt(tte)) 
                    + interest_rate * strike * math.exp(-interest_rate * tte) * norm.cdf(-d2)) / 365
        
        gamma = norm.pdf(d1) / (spot_price * iv * math.sqrt(tte))
        vega = spot_price * norm.pdf(d1) * math.sqrt(tte) / 100
        
        return Greeks(
            delta=round(delta, 4),
            gamma=round(gamma, 6),
            theta=round(theta, 4),
            vega=round(vega, 4),
            iv=round(iv * 100, 2)
        )
```

### 5. WebSocket Manager

```python
class WebSocketManager:
    """Manages WebSocket connections for real-time data"""
    
    def __init__(self, broker: BrokerAdapter):
        self.broker = broker
        self.clients: Dict[str, WebSocket] = {}  # client_id -> websocket
        self.subscriptions: Dict[str, Set[str]] = {}  # symbol_key -> set of client_ids
        self.broker_ws: Optional[websockets.WebSocketClientProtocol] = None
        self._authenticated = False
    
    async def connect_to_broker(self, auth_token: str, feed_token: str):
        """Establish connection to broker WebSocket"""
        config = self.broker.get_websocket_config()
        
        self.broker_ws = await websockets.connect(config["url"])
        
        # Authenticate
        auth_msg = {
            "action": "authenticate",
            "auth_token": auth_token,
            "feed_token": feed_token
        }
        await self.broker_ws.send(json.dumps(auth_msg))
        
        # Start listening
        asyncio.create_task(self._listen_broker())
    
    async def _listen_broker(self):
        """Listen for messages from broker WebSocket"""
        async for message in self.broker_ws:
            data = json.loads(message)
            
            if data.get("type") == "market_data":
                symbol_key = f"{data['symbol']}:{data['exchange']}"
                
                # Broadcast to subscribed clients
                if symbol_key in self.subscriptions:
                    for client_id in self.subscriptions[symbol_key]:
                        if client_id in self.clients:
                            await self.clients[client_id].send_json({
                                "type": "market_data",
                                "symbol": data["symbol"],
                                "exchange": data["exchange"],
                                "data": data["data"]
                            })
    
    async def handle_client(self, websocket: WebSocket, client_id: str):
        """Handle individual client WebSocket connection"""
        await websocket.accept()
        self.clients[client_id] = websocket
        
        try:
            async for message in websocket.iter_json():
                action = message.get("action")
                
                if action == "subscribe":
                    await self._subscribe(
                        client_id,
                        message["symbol"],
                        message.get("exchange", "NSE")
                    )
                elif action == "unsubscribe":
                    await self._unsubscribe(
                        client_id,
                        message["symbol"],
                        message.get("exchange", "NSE")
                    )
        finally:
            await self._cleanup_client(client_id)
    
    async def _subscribe(self, client_id: str, symbol: str, exchange: str):
        """Subscribe client to symbol updates"""
        symbol_key = f"{symbol}:{exchange}"
        
        if symbol_key not in self.subscriptions:
            self.subscriptions[symbol_key] = set()
            # Subscribe to broker
            await self.broker_ws.send(json.dumps({
                "action": "subscribe",
                "symbol": symbol,
                "exchange": exchange,
                "mode": 2
            }))
        
        self.subscriptions[symbol_key].add(client_id)
```

## Data Models

### Database Schema

```python
from sqlalchemy import Column, Integer, String, Float, DateTime, Index, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class OHLCHistory(Base):
    """Historical OHLC candle data"""
    __tablename__ = "ohlc_history"
    
    id = Column(Integer, primary_key=True)
    symbol = Column(String(50), nullable=False)
    exchange = Column(String(10), nullable=False)
    interval = Column(String(20), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Integer, default=0)
    
    __table_args__ = (
        UniqueConstraint('symbol', 'exchange', 'interval', 'timestamp'),
        Index('idx_symbol_exchange_interval', 'symbol', 'exchange', 'interval'),
        Index('idx_timestamp', 'timestamp'),
    )

class UserSession(Base):
    """User authentication sessions"""
    __tablename__ = "user_sessions"
    
    id = Column(Integer, primary_key=True)
    api_key = Column(String(100), unique=True, nullable=False)
    broker = Column(String(20), nullable=False)
    client_id = Column(String(50), nullable=False)
    jwt_token = Column(String(500))
    refresh_token = Column(String(500))
    feed_token = Column(String(200))
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)
    
    __table_args__ = (
        Index('idx_api_key', 'api_key'),
    )

class InstrumentMaster(Base):
    """Instrument master data"""
    __tablename__ = "instrument_master"
    
    id = Column(Integer, primary_key=True)
    symbol = Column(String(50), nullable=False)
    token = Column(String(20), nullable=False)
    name = Column(String(100))
    exchange = Column(String(10), nullable=False)
    instrument_type = Column(String(20))
    lot_size = Column(Integer, default=1)
    tick_size = Column(Float, default=0.05)
    expiry = Column(String(20))
    strike = Column(Float)
    option_type = Column(String(5))
    updated_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint('symbol', 'exchange'),
        Index('idx_symbol_search', 'symbol'),
        Index('idx_token', 'token', 'exchange'),
    )
```



## API Endpoints (OpenAlgo Compatible)

### Authentication

```
POST /api/v1/auth/login
Request: { broker: "angelone", client_id, password, totp, api_key }
Response: { status: "success", data: { apikey: "generated_key" } }
```

### Historical Data

```
POST /api/v1/history
Request: { apikey, symbol, exchange, interval, start_date, end_date }
Response: { 
    status: "success", 
    data: [
        { timestamp: 1234567890, open, high, low, close, volume },
        ...
    ]
}
```

### Quotes

```
POST /api/v1/quotes
Request: { apikey, symbol, exchange }
Response: {
    status: "success",
    data: { ltp, open, high, low, prev_close, volume }
}
```

### Option Chain

```
POST /api/v1/optionchain
Request: { apikey, underlying, exchange, expiry?, strike_count? }
Response: {
    status: "success",
    data: {
        underlying, underlyingLTP, atmStrike, expiryDate,
        chain: [
            { strike, ce: { symbol, ltp, oi, volume, bid, ask }, pe: {...} }
        ]
    }
}
```

### Option Greeks

```
POST /api/v1/greeks
Request: { apikey, symbol, exchange }
Response: {
    status: "success",
    data: { delta, gamma, theta, vega, iv }
}

POST /api/v1/greeks/batch
Request: { apikey, symbols: [{ symbol, exchange }] }
Response: {
    status: "success",
    data: [{ symbol, delta, gamma, theta, vega, iv }, ...]
}
```

### Expiry Dates

```
POST /api/v1/expiry
Request: { apikey, underlying, exchange, instrumenttype }
Response: {
    status: "success",
    data: ["09JAN26", "16JAN26", "23JAN26", ...]
}
```

### Symbol Search

```
POST /api/v1/search
Request: { apikey, query, exchange? }
Response: {
    status: "success",
    data: [
        { symbol, name, exchange, token, instrument_type, lot_size }
    ]
}
```

### Market Timings

```
POST /api/v1/market/timings
Request: { apikey, date }
Response: {
    status: "success",
    data: [
        { exchange: "NSE", start_time: epoch_ms, end_time: epoch_ms }
    ]
}

POST /api/v1/market/holidays
Request: { apikey, year }
Response: {
    status: "success",
    data: [
        { date, description, holiday_type, closed_exchanges }
    ]
}
```

### WebSocket Protocol

```
Connect: ws://localhost:8765

Authentication:
→ { action: "authenticate", api_key: "..." }
← { type: "auth", status: "success" }

Subscribe:
→ { action: "subscribe", symbol: "NIFTY", exchange: "NSE", mode: 2 }
← { type: "market_data", symbol: "NIFTY", exchange: "NSE", data: { ltp, ... } }

Unsubscribe:
→ { action: "unsubscribe", symbol: "NIFTY", exchange: "NSE" }

Heartbeat:
← { type: "ping" }
→ { type: "pong" }
```

## Project Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app entry point
│   ├── config.py               # Configuration settings
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── deps.py             # Dependency injection
│   │   ├── v1/
│   │   │   ├── __init__.py
│   │   │   ├── router.py       # API router
│   │   │   ├── auth.py         # Auth endpoints
│   │   │   ├── history.py      # Historical data endpoints
│   │   │   ├── quotes.py       # Quote endpoints
│   │   │   ├── optionchain.py  # Option chain endpoints
│   │   │   ├── greeks.py       # Greeks endpoints
│   │   │   ├── market.py       # Market timings endpoints
│   │   │   └── search.py       # Symbol search endpoints
│   │   └── websocket.py        # WebSocket handler
│   │
│   ├── brokers/
│   │   ├── __init__.py
│   │   ├── base.py             # BrokerAdapter ABC
│   │   ├── angelone/
│   │   │   ├── __init__.py
│   │   │   ├── adapter.py      # AngelOneAdapter
│   │   │   ├── auth.py         # Auth helpers
│   │   │   ├── endpoints.py    # API endpoint constants
│   │   │   └── transformers.py # Response transformers
│   │   └── factory.py          # Broker factory
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── market_data.py      # MarketDataService
│   │   ├── option.py           # OptionService
│   │   ├── auth.py             # AuthService
│   │   └── symbol.py           # SymbolService
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── database.py         # SQLAlchemy models
│   │   └── schemas.py          # Pydantic schemas
│   │
│   ├── db/
│   │   ├── __init__.py
│   │   ├── session.py          # Database session
│   │   └── migrations/         # Alembic migrations
│   │
│   ├── websocket/
│   │   ├── __init__.py
│   │   └── manager.py          # WebSocketManager
│   │
│   └── utils/
│       ├── __init__.py
│       ├── greeks.py           # Black-Scholes calculations
│       ├── cache.py            # Redis cache helpers
│       └── logger.py           # Logging setup
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_brokers/
│   ├── test_services/
│   └── test_api/
│
├── alembic.ini
├── requirements.txt
├── docker-compose.yml
└── README.md
```

## Error Handling

### Error Response Format

```python
class ErrorResponse(BaseModel):
    status: str = "error"
    code: str
    message: str
    details: Optional[Dict] = None

# Error codes
ERROR_CODES = {
    "AUTH_FAILED": "Authentication failed",
    "INVALID_TOKEN": "Invalid or expired token",
    "RATE_LIMITED": "Rate limit exceeded",
    "BROKER_ERROR": "Broker API error",
    "SYMBOL_NOT_FOUND": "Symbol not found",
    "INVALID_INTERVAL": "Invalid interval",
    "NO_DATA": "No data available",
    "INTERNAL_ERROR": "Internal server error"
}
```

### Angel One Error Code Mapping

```python
ANGELONE_ERROR_MAP = {
    "AB1000": ("AUTH_FAILED", "Invalid credentials"),
    "AB1001": ("INVALID_TOKEN", "Session expired"),
    "AB1002": ("RATE_LIMITED", "Too many requests"),
    "AB1004": ("BROKER_ERROR", "Something went wrong"),
    "AB2000": ("SYMBOL_NOT_FOUND", "Invalid symbol token"),
}
```

## Testing Strategy

### Unit Tests
- Test each broker adapter method independently
- Test service layer business logic
- Test data transformations
- Mock external API calls

### Property-Based Tests
- Test OHLC data transformation preserves data integrity
- Test Greeks calculations within valid ranges
- Test WebSocket message routing

### Integration Tests
- Test full API request/response cycle
- Test database operations
- Test WebSocket connections



## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: OHLC Data Transformation Preserves Integrity

*For any* broker response containing OHLC candle data, transforming it to standardized format SHALL preserve all numeric values (open, high, low, close, volume) and timestamps without data loss or corruption.

**Validates: Requirements 3.5, 10.2**

### Property 2: Price Change Calculation Correctness

*For any* quote with LTP and prev_close values where prev_close > 0, the calculated change SHALL equal (LTP - prev_close) and change_percent SHALL equal ((LTP - prev_close) / prev_close * 100).

**Validates: Requirements 4.2**

### Property 3: Quote Response Completeness

*For any* valid quote request for supported exchanges (NSE, BSE, NFO, BFO, MCX), the response SHALL contain all required fields: ltp, open, high, low, prev_close, and volume.

**Validates: Requirements 4.1, 4.3**

### Property 4: Interval Support Validation

*For any* valid interval from the set {1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 1d, 1w, 1M}, the Market_Data_Service SHALL accept and process the historical data request without error.

**Validates: Requirements 3.2**

### Property 5: Cache-First Data Fetching

*For any* historical data request where partial data exists in cache, the service SHALL fetch only the missing date ranges from the broker, not the entire requested range.

**Validates: Requirements 3.4**

### Property 6: Timestamp Timezone Consistency

*For any* timestamp converted from broker format to IST, converting back SHALL produce the original timestamp (round-trip property).

**Validates: Requirements 3.6**

### Property 7: WebSocket Subscription Routing

*For any* symbol with N subscribed clients, when a tick arrives for that symbol, exactly N clients SHALL receive the tick. When a client unsubscribes and no other clients remain subscribed, the symbol SHALL be unsubscribed from broker feed.

**Validates: Requirements 5.2, 5.5, 5.6**

### Property 8: Option Chain Data Completeness

*For any* option chain request, each strike in the response SHALL contain both CE and PE data (or null if not available), and each option SHALL include: symbol, ltp, oi, volume, bid, ask fields.

**Validates: Requirements 6.1, 6.2**

### Property 9: ATM Strike Identification

*For any* underlying LTP and list of available strikes, the identified ATM strike SHALL be the strike with minimum absolute difference from the underlying LTP.

**Validates: Requirements 6.3**

### Property 10: Expiry Filtering Correctness

*For any* option chain request with specified expiry date, all returned options SHALL have that exact expiry date.

**Validates: Requirements 6.4**

### Property 11: Greeks Calculation Validity

*For any* option with valid inputs (spot > 0, strike > 0, time_to_expiry > 0, iv > 0), calculated Greeks SHALL satisfy: -1 <= delta <= 1, gamma >= 0, vega >= 0, and IV > 0.

**Validates: Requirements 7.1, 7.2, 7.5**

### Property 12: Market Open/Closed Status

*For any* given timestamp and exchange, the is_market_open function SHALL return true if and only if the timestamp falls within the exchange's trading hours for that day and the day is not a holiday.

**Validates: Requirements 8.1, 8.3**

### Property 13: Database Duplicate Handling

*For any* OHLC candle with same (symbol, exchange, interval, timestamp), inserting it multiple times SHALL not create duplicate entries and SHALL not raise an error.

**Validates: Requirements 9.5**

### Property 14: Cache TTL Expiration

*For any* cached data with TTL, querying after TTL expiration SHALL trigger a fresh fetch from the source.

**Validates: Requirements 9.3**

### Property 15: Error Response Standardization

*For any* broker API error, the backend SHALL return a response with status="error", a valid error code from the defined set, and a human-readable message.

**Validates: Requirements 11.1, 11.5**

### Property 16: Rate Limiting Enforcement

*For any* sequence of N requests within time window T where N exceeds the rate limit, requests beyond the limit SHALL either be queued or return a rate limit error.

**Validates: Requirements 11.3, 11.4**

### Property 17: Symbol Search Relevance

*For any* search query, returned symbols SHALL contain the query string (case-insensitive) in either symbol name or trading symbol, and results SHALL include lot_size, tick_size, and instrument_type.

**Validates: Requirements 12.1, 12.4, 12.5**

### Property 18: Token Refresh Before Expiry

*For any* JWT token approaching expiry (within 5 minutes), the adapter SHALL automatically refresh the token before making the next API call.

**Validates: Requirements 2.3**

### Property 19: Authentication Error Mapping

*For any* failed authentication attempt, the error response SHALL contain the original broker error code and a mapped user-friendly message.

**Validates: Requirements 2.4**

