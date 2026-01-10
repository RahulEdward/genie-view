# Implementation Plan: Modular Trading Backend

## Overview

Yeh implementation plan FastAPI backend ko incrementally build karega. Pehle core infrastructure, phir broker adapter, services, aur finally API endpoints. Har task previous tasks pe build karta hai.

## Tasks

- [x] 1. Project Setup and Core Infrastructure
  - [x] 1.1 Initialize FastAPI project with folder structure
    - Create `backend/` directory with `app/`, `tests/`, config files
    - Setup `requirements.txt` with FastAPI, uvicorn, httpx, sqlalchemy, asyncpg, redis, pydantic
    - Create `app/main.py` with basic FastAPI app
    - Create `app/config.py` with settings using pydantic-settings
    - _Requirements: 1.1, 1.3_

  - [x] 1.2 Setup PostgreSQL database models and migrations
    - Create `app/db/session.py` with async SQLAlchemy engine
    - Create `app/models/database.py` with OHLCHistory, UserSession, InstrumentMaster models
    - Setup Alembic for migrations
    - Create initial migration
    - _Requirements: 9.1, 9.2, 9.4_

  - [x] 1.3 Setup Redis cache connection
    - Create `app/utils/cache.py` with Redis async client
    - Add cache helper functions (get, set, setex, delete)
    - _Requirements: 9.3_

  - [x] 1.4 Setup logging and error handling
    - Create `app/utils/logger.py` with structured logging
    - Create `app/models/schemas.py` with ErrorResponse, standard response models
    - Create error handler middleware
    - _Requirements: 11.1, 11.2_

- [x] 2. Broker Adapter Layer
  - [x] 2.1 Create BrokerAdapter abstract base class
    - Create `app/brokers/base.py` with BrokerAdapter ABC
    - Define all abstract methods: authenticate, refresh_token, get_historical_data, get_quote, get_option_chain, get_expiry_dates, search_symbols, get_instrument_master, get_websocket_config
    - Create Pydantic models: OHLCCandle, Quote, OptionData, Greeks
    - _Requirements: 1.1, 1.2_

  - [x] 2.2 Implement AngelOneAdapter authentication
    - Create `app/brokers/angelone/endpoints.py` with API URLs and constants
    - Create `app/brokers/angelone/adapter.py` with AngelOneAdapter class
    - Implement `authenticate()` method with TOTP login
    - Implement `refresh_token()` method
    - Implement `_get_headers()` helper
    - _Requirements: 2.1, 2.2, 2.3, 2.5_

  - [x] 2.3 Write property test for authentication error mapping
    - **Property 19: Authentication Error Mapping**
    - Test that failed auth returns broker error code and user-friendly message
    - **Validates: Requirements 2.4**

  - [x] 2.4 Implement AngelOneAdapter historical data
    - Implement `get_historical_data()` method
    - Create `app/brokers/angelone/transformers.py` for response transformation
    - Implement interval mapping (1m → ONE_MINUTE, etc.)
    - Implement symbol token lookup helper
    - _Requirements: 3.1, 3.2_

  - [x] 2.5 Write property test for OHLC transformation
    - **Property 1: OHLC Data Transformation Preserves Integrity**
    - Test that transformation preserves all numeric values
    - **Validates: Requirements 3.5, 10.2**

  - [x] 2.6 Implement AngelOneAdapter quotes and LTP
    - Implement `get_quote()` method
    - Implement `get_ltp()` method for batch LTP
    - _Requirements: 4.1, 4.3_

  - [x] 2.7 Implement AngelOneAdapter option chain
    - Implement `get_option_chain()` method
    - Implement `get_expiry_dates()` method
    - _Requirements: 6.1, 6.4, 6.5, 6.6_

  - [x] 2.8 Implement AngelOneAdapter symbol search
    - Implement `search_symbols()` method
    - Implement `get_instrument_master()` method
    - _Requirements: 12.1, 12.2_

  - [x] 2.9 Create broker factory
    - Create `app/brokers/factory.py` with `get_broker()` function
    - Support runtime broker selection from config
    - _Requirements: 1.3_

- [x] 3. Checkpoint - Broker Adapter Complete
  - Ensure all broker adapter methods work
  - Test with real Angel One credentials
  - Ask user if questions arise

- [x] 4. Service Layer
  - [x] 4.1 Implement AuthService
    - Create `app/services/auth.py` with AuthService class
    - Implement login with session storage
    - Implement API key generation and validation
    - Implement token refresh logic
    - _Requirements: 2.2, 2.3, 2.5, 10.3_

  - [x] 4.2 Write property test for token refresh
    - **Property 18: Token Refresh Before Expiry**
    - Test that tokens are refreshed before expiry
    - **Validates: Requirements 2.3**

  - [x] 4.3 Implement MarketDataService historical data
    - Create `app/services/market_data.py` with MarketDataService class
    - Implement `get_history()` with database caching
    - Implement `_find_missing_ranges()` for smart fetching
    - Implement `_store_candles()` for database storage
    - _Requirements: 3.1, 3.3, 3.4_

  - [x] 4.4 Write property test for cache-first fetching
    - **Property 5: Cache-First Data Fetching**
    - Test that only missing ranges are fetched
    - **Validates: Requirements 3.4**

  - [x] 4.5 Write property test for timestamp conversion
    - **Property 6: Timestamp Timezone Consistency**
    - Test round-trip timestamp conversion
    - **Validates: Requirements 3.6**

  - [x] 4.6 Implement MarketDataService quotes
    - Implement `get_quote()` with change calculation
    - Implement fallback to cached quote on error
    - _Requirements: 4.1, 4.2, 4.4_

  - [x] 4.7 Write property test for price change calculation
    - **Property 2: Price Change Calculation Correctness**
    - Test mathematical correctness of change calculation
    - **Validates: Requirements 4.2**

  - [x] 4.8 Implement OptionService
    - Create `app/services/option.py` with OptionService class
    - Implement `get_option_chain()` with ATM identification
    - Implement `get_expiry_dates()`
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

  - [x] 4.9 Write property test for ATM strike identification
    - **Property 9: ATM Strike Identification**
    - Test that ATM is closest strike to underlying LTP
    - **Validates: Requirements 6.3**

  - [x] 4.10 Write property test for option chain completeness
    - **Property 8: Option Chain Data Completeness**
    - Test that all required fields are present
    - **Validates: Requirements 6.1, 6.2**

  - [x] 4.11 Implement Greeks calculation
    - Create `app/utils/greeks.py` with Black-Scholes implementation
    - Implement `calculate_iv()` using Newton-Raphson
    - Implement `calculate_greeks()` for delta, gamma, theta, vega
    - Add batch Greeks calculation
    - _Requirements: 7.1, 7.2, 7.4, 7.5_

  - [x] 4.12 Write property test for Greeks validity
    - **Property 11: Greeks Calculation Validity**
    - Test that Greeks are within valid ranges
    - **Validates: Requirements 7.1, 7.2, 7.5**

  - [x] 4.13 Implement SymbolService
    - Create `app/services/symbol.py` with SymbolService class
    - Implement `search()` with fuzzy matching
    - Implement `refresh_master()` for daily refresh
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5_

  - [x] 4.14 Write property test for symbol search
    - **Property 17: Symbol Search Relevance**
    - Test that results contain query and required fields
    - **Validates: Requirements 12.1, 12.4, 12.5**

  - [x] 4.15 Implement MarketTimingService
    - Create `app/services/market_timing.py`
    - Implement `get_timings()` for exchange timings
    - Implement `get_holidays()` for holiday list
    - Implement `is_market_open()`
    - _Requirements: 8.1, 8.2, 8.3, 8.4_

  - [x] 4.16 Write property test for market open status
    - **Property 12: Market Open/Closed Status**
    - Test that status is correct based on time and holidays
    - **Validates: Requirements 8.1, 8.3**

- [x] 5. Checkpoint - Services Complete
  - Ensure all services work correctly
  - Run all property tests
  - Ask user if questions arise

- [x] 6. API Layer
  - [x] 6.1 Setup API router and dependencies
    - Create `app/api/deps.py` with dependency injection
    - Create `app/api/v1/router.py` with main router
    - Setup API key validation middleware
    - _Requirements: 10.1, 10.3_

  - [x] 6.2 Implement auth endpoints
    - Create `app/api/v1/auth.py`
    - POST `/api/v1/auth/login` - broker login
    - POST `/api/v1/auth/logout` - logout
    - _Requirements: 2.2, 10.3_

  - [x] 6.3 Implement history endpoint
    - Create `app/api/v1/history.py`
    - POST `/api/v1/history` - get historical OHLC
    - Match OpenAlgo request/response format
    - _Requirements: 3.1, 10.1, 10.2_

  - [x] 6.4 Implement quotes endpoint
    - Create `app/api/v1/quotes.py`
    - POST `/api/v1/quotes` - get current quote
    - Match OpenAlgo response format
    - _Requirements: 4.1, 10.1, 10.2_

  - [x] 6.5 Write property test for quote response completeness
    - **Property 3: Quote Response Completeness**
    - Test that all required fields are present
    - **Validates: Requirements 4.1, 4.3**

  - [x] 6.6 Implement option chain endpoint
    - Create `app/api/v1/optionchain.py`
    - POST `/api/v1/optionchain` - get option chain
    - Match OpenAlgo response format
    - _Requirements: 6.1, 10.1, 10.2_

  - [x] 6.7 Write property test for expiry filtering
    - **Property 10: Expiry Filtering Correctness**
    - Test that only specified expiry data is returned
    - **Validates: Requirements 6.4**

  - [x] 6.8 Implement Greeks endpoints
    - Create `app/api/v1/greeks.py`
    - POST `/api/v1/greeks` - single option Greeks
    - POST `/api/v1/greeks/batch` - batch Greeks
    - _Requirements: 7.1, 7.5, 10.1_

  - [x] 6.9 Implement expiry endpoint
    - POST `/api/v1/expiry` - get expiry dates
    - _Requirements: 6.5, 10.1_

  - [x] 6.10 Implement search endpoint
    - Create `app/api/v1/search.py`
    - POST `/api/v1/search` - symbol search
    - _Requirements: 12.1, 10.1_

  - [x] 6.11 Implement market endpoints
    - Create `app/api/v1/market.py`
    - POST `/api/v1/market/timings` - exchange timings
    - POST `/api/v1/market/holidays` - holiday list
    - _Requirements: 8.1, 8.2, 10.1_

  - [x] 6.12 Implement rate limiting middleware
    - Create rate limiter using Redis
    - Apply to all API endpoints
    - _Requirements: 11.3, 11.4_

  - [x] 6.13 Write property test for rate limiting
    - **Property 16: Rate Limiting Enforcement**
    - Test that excess requests are rejected/queued
    - **Validates: Requirements 11.3, 11.4**

  - [x] 6.14 Write property test for error response standardization
    - **Property 15: Error Response Standardization**
    - Test that errors have status, code, message
    - **Validates: Requirements 11.1, 11.5**

- [x] 7. Checkpoint - API Layer Complete
  - Test all API endpoints with Postman/curl
  - Verify OpenAlgo compatibility
  - Ask user if questions arise

- [x] 8. WebSocket Layer
  - [x] 8.1 Implement WebSocketManager
    - Create `app/websocket/manager.py` with WebSocketManager class
    - Implement client connection handling
    - Implement subscription management
    - _Requirements: 5.1, 5.2_

  - [x] 8.2 Implement broker WebSocket connection
    - Connect to Angel One WebSocket feed
    - Handle authentication
    - Handle reconnection on disconnect
    - _Requirements: 5.1, 5.4_

  - [x] 8.3 Implement subscription routing
    - Route ticks to subscribed clients
    - Handle subscribe/unsubscribe messages
    - Cleanup on client disconnect
    - _Requirements: 5.2, 5.3, 5.5, 5.6_

  - [x] 8.4 Write property test for subscription routing
    - **Property 7: WebSocket Subscription Routing**
    - Test that ticks go to correct subscribers
    - **Validates: Requirements 5.2, 5.5, 5.6**

  - [x] 8.5 Setup WebSocket endpoint
    - Create `app/api/websocket.py`
    - WS `/ws` - WebSocket endpoint
    - Handle ping/pong heartbeat
    - _Requirements: 5.1, 10.4_

- [x] 9. Database Operations
  - [x] 9.1 Implement OHLC storage with deduplication
    - Add upsert logic for OHLC candles
    - Handle duplicate timestamps gracefully
    - _Requirements: 9.1, 9.5_

  - [x] 9.2 Write property test for duplicate handling
    - **Property 13: Database Duplicate Handling**
    - Test that duplicates don't create errors
    - **Validates: Requirements 9.5**

  - [x] 9.3 Implement cache TTL for option chain
    - Add TTL-based caching for option chain
    - Auto-expire after configured time
    - _Requirements: 9.3_

  - [x] 9.4 Write property test for cache TTL
    - **Property 14: Cache TTL Expiration**
    - Test that expired cache triggers fresh fetch
    - **Validates: Requirements 9.3**

- [x] 10. Final Integration
  - [x] 10.1 Create docker-compose.yml
    - Setup PostgreSQL container
    - Setup Redis container
    - Setup backend container
    - _Requirements: 9.4_

  - [x] 10.2 Create startup script
    - Run migrations on startup
    - Initialize instrument master
    - Start WebSocket connection
    - _Requirements: 12.2, 12.3_

  - [x] 10.3 Write integration tests
    - Test full API flow
    - Test WebSocket flow
    - Test with mock broker responses
    - _Requirements: 10.1, 10.4_

- [x] 11. Final Checkpoint
  - Run all tests
  - Test with frontend app
  - Ensure all requirements are met
  - Ask user if questions arise

## Notes

- All tasks including property-based tests are required
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties
- Unit tests validate specific examples and edge cases
