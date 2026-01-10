# Requirements Document

## Introduction

Yeh document ek modular FastAPI backend ke requirements define karta hai jo Angel One broker se live data, historical data, options data aur Greeks fetch karega. Backend ko is tarah design karna hai ki future mein easily naye brokers add ho sakein bina existing code ko modify kiye. Frontend app (React) ke saath seamlessly integrate hoga jo currently OpenAlgo API use karti hai.

## Glossary

- **Backend**: FastAPI-based server jo broker APIs se data fetch karke frontend ko provide karega
- **Broker_Adapter**: Abstract interface jo har broker ke liye implement hoga (Angel One, Zerodha, etc.)
- **Angel_One_Adapter**: Angel One broker ka specific implementation
- **Market_Data_Service**: Service jo live aur historical market data handle karega
- **Option_Service**: Service jo option chain, Greeks aur option-related data handle karega
- **WebSocket_Manager**: Real-time data streaming ke liye WebSocket connections manage karega
- **Database**: PostgreSQL database jo historical data, user sessions aur cache store karega
- **Greeks**: Option pricing metrics (Delta, Gamma, Theta, Vega, IV)
- **LTP**: Last Traded Price
- **OI**: Open Interest
- **OHLC**: Open, High, Low, Close candle data

## Requirements

### Requirement 1: Modular Broker Architecture

**User Story:** As a developer, I want a modular broker architecture, so that I can easily add new brokers without modifying existing code.

#### Acceptance Criteria

1. THE Backend SHALL define a Broker_Adapter abstract interface with methods for authentication, market data, historical data, and option chain
2. WHEN a new broker is added, THE Backend SHALL only require implementing the Broker_Adapter interface without modifying core services
3. THE Backend SHALL support runtime broker selection based on configuration
4. THE Backend SHALL maintain separate configuration files for each broker's credentials and settings

### Requirement 2: Angel One Broker Integration

**User Story:** As a trader, I want to connect to Angel One broker, so that I can access live market data and trade.

#### Acceptance Criteria

1. THE Angel_One_Adapter SHALL implement the Broker_Adapter interface using Angel One REST APIs directly (no SDK)
2. WHEN authenticating, THE Angel_One_Adapter SHALL call REST endpoint with client ID, password, and TOTP token
3. THE Angel_One_Adapter SHALL handle JWT token refresh automatically before expiry
4. IF authentication fails, THEN THE Angel_One_Adapter SHALL return descriptive error messages with Angel One error codes
5. THE Angel_One_Adapter SHALL store JWT and refresh tokens securely in database
6. THE Angel_One_Adapter SHALL use httpx/aiohttp for async HTTP requests to Angel One REST endpoints

### Requirement 3: Historical Data Fetching

**User Story:** As a trader, I want to fetch historical OHLC data, so that I can view charts and analyze price movements.

#### Acceptance Criteria

1. WHEN requesting historical data, THE Market_Data_Service SHALL fetch OHLC candles from the broker
2. THE Market_Data_Service SHALL support multiple intervals: 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 1d, 1w, 1M
3. THE Market_Data_Service SHALL cache historical data in Database to reduce broker API calls
4. WHEN cached data exists, THE Market_Data_Service SHALL return cached data and fetch only missing candles
5. THE Market_Data_Service SHALL transform broker-specific response format to standardized OHLC format
6. THE Market_Data_Service SHALL handle IST timezone conversion for timestamps

### Requirement 4: Live Market Data (Quotes)

**User Story:** As a trader, I want to see real-time price quotes, so that I can make informed trading decisions.

#### Acceptance Criteria

1. WHEN requesting quotes, THE Market_Data_Service SHALL return LTP, open, high, low, previous close, and volume
2. THE Market_Data_Service SHALL calculate price change and percentage change from previous close
3. THE Market_Data_Service SHALL support quotes for NSE, BSE, NFO, BFO, MCX exchanges
4. IF quote request fails, THEN THE Market_Data_Service SHALL return cached last known quote with stale indicator

### Requirement 5: WebSocket Real-time Streaming

**User Story:** As a trader, I want real-time price updates via WebSocket, so that I can see live price movements without refreshing.

#### Acceptance Criteria

1. THE WebSocket_Manager SHALL establish connection with broker's WebSocket feed
2. WHEN client subscribes to symbols, THE WebSocket_Manager SHALL forward real-time ticks to connected clients
3. THE WebSocket_Manager SHALL support multiple subscription modes: LTP only, Quote, Full depth
4. THE WebSocket_Manager SHALL handle automatic reconnection on connection drop
5. WHEN client disconnects, THE WebSocket_Manager SHALL unsubscribe from symbols no longer needed
6. THE WebSocket_Manager SHALL broadcast to multiple frontend clients subscribed to same symbol

### Requirement 6: Option Chain Data

**User Story:** As an options trader, I want to view option chain with all strikes, so that I can analyze and select options.

#### Acceptance Criteria

1. WHEN requesting option chain, THE Option_Service SHALL return all strikes with CE and PE data
2. THE Option_Service SHALL include LTP, OI, volume, bid, ask for each option
3. THE Option_Service SHALL identify ATM strike based on underlying LTP
4. THE Option_Service SHALL support filtering by expiry date
5. THE Option_Service SHALL return available expiry dates for an underlying
6. THE Option_Service SHALL support both index options (NIFTY, BANKNIFTY) and stock options

### Requirement 7: Option Greeks Calculation

**User Story:** As an options trader, I want to see Greeks for options, so that I can understand risk and pricing.

#### Acceptance Criteria

1. THE Option_Service SHALL calculate or fetch Delta, Gamma, Theta, Vega for each option
2. THE Option_Service SHALL calculate Implied Volatility (IV) for each option
3. WHEN broker provides Greeks, THE Option_Service SHALL use broker-provided values
4. WHEN broker does not provide Greeks, THE Option_Service SHALL calculate using Black-Scholes model
5. THE Option_Service SHALL support batch Greeks calculation for multiple options

### Requirement 8: Market Timings and Holidays

**User Story:** As a trader, I want to know market timings and holidays, so that I can plan my trading.

#### Acceptance Criteria

1. THE Backend SHALL provide market timings for each exchange (NSE, BSE, NFO, MCX)
2. THE Backend SHALL provide list of trading holidays for a given year
3. THE Backend SHALL indicate if market is currently open or closed
4. THE Backend SHALL handle special trading sessions (Muhurat trading, etc.)

### Requirement 9: Database Storage

**User Story:** As a system, I want to store data in database, so that I can reduce API calls and provide faster responses.

#### Acceptance Criteria

1. THE Database SHALL store historical OHLC data with symbol, exchange, interval, and timestamp
2. THE Database SHALL store user sessions and authentication tokens
3. THE Database SHALL store cached option chain data with TTL
4. THE Database SHALL use PostgreSQL with proper indexing for fast queries
5. WHEN storing data, THE Database SHALL handle duplicate entries gracefully

### Requirement 10: API Compatibility with Frontend

**User Story:** As a frontend developer, I want backend APIs to match existing OpenAlgo format, so that minimal frontend changes are needed.

#### Acceptance Criteria

1. THE Backend SHALL expose REST endpoints matching OpenAlgo API structure
2. THE Backend SHALL return responses in same JSON format as OpenAlgo
3. THE Backend SHALL support same authentication flow (API key based)
4. THE Backend SHALL expose WebSocket endpoint compatible with frontend's SharedWebSocketManager
5. WHEN migrating from OpenAlgo, THE Frontend SHALL require only URL configuration change

### Requirement 11: Error Handling and Logging

**User Story:** As a developer, I want proper error handling and logging, so that I can debug issues easily.

#### Acceptance Criteria

1. IF any broker API call fails, THEN THE Backend SHALL return standardized error response with code and message
2. THE Backend SHALL log all API requests and responses for debugging
3. THE Backend SHALL implement rate limiting to prevent broker API abuse
4. IF rate limit is exceeded, THEN THE Backend SHALL queue requests or return appropriate error
5. THE Backend SHALL handle broker-specific error codes and translate to user-friendly messages

### Requirement 12: Symbol Search and Master Data

**User Story:** As a trader, I want to search for symbols, so that I can find instruments to trade.

#### Acceptance Criteria

1. THE Backend SHALL provide symbol search endpoint with fuzzy matching
2. THE Backend SHALL cache instrument master data from broker
3. THE Backend SHALL refresh instrument master data daily
4. THE Backend SHALL support search across all exchanges (NSE, BSE, NFO, BFO, MCX, CDS)
5. THE Backend SHALL return symbol details including lot size, tick size, and instrument type
