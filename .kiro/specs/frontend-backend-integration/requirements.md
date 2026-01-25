# Requirements Document: Frontend-Backend Integration

## Introduction

Yeh document frontend trading dashboard ke sabhi features ko AngelOne broker backend se properly connect karne ke requirements define karta hai. Dashboard mein bahut se features hain jo currently backend se connected nahi hain ya properly kaam nahi kar rahe. Is spec ka goal hai ki har feature perfectly work kare bina kisi functionality ko nuksan diye.

## Glossary

- **Frontend**: React-based trading dashboard with charts, watchlist, option chain, account panel, etc.
- **Backend**: FastAPI-based server jo AngelOne broker se data fetch karta hai
- **Integration**: Frontend aur backend ke beech proper connection aur data flow
- **WebSocket**: Real-time data streaming ke liye connection
- **API_Service**: Frontend service files jo backend APIs ko call karti hain
- **Account_Panel**: Dashboard component jo funds, positions, orders, trades dikhata hai
- **Option_Chain**: Component jo option chain data dikhata hai
- **Chart**: TradingView-style chart component
- **Watchlist**: Symbol watchlist component
- **Market_Data**: Live quotes, historical data, ticks

## Requirements

### Requirement 1: Account Panel Integration

**User Story:** As a trader, I want to see my account details, funds, positions, orders, and trades in the dashboard, so that I can monitor my trading activity.

#### Acceptance Criteria

1. WHEN user logs in, THE Account_Panel SHALL fetch and display account funds from backend
2. WHEN user opens positions tab, THE Account_Panel SHALL fetch and display current positions with live P&L
3. WHEN user opens orders tab, THE Account_Panel SHALL fetch and display all orders with status
4. WHEN user opens trades tab, THE Account_Panel SHALL fetch and display executed trades
5. WHEN user opens holdings tab, THE Account_Panel SHALL fetch and display long-term holdings
6. THE Account_Panel SHALL refresh data every 5 seconds for live updates
7. IF backend API fails, THEN THE Account_Panel SHALL show cached data with stale indicator

### Requirement 2: Live Market Data Integration

**User Story:** As a trader, I want to see live price updates for symbols in my watchlist and charts, so that I can make informed trading decisions.

#### Acceptance Criteria

1. WHEN user adds symbol to watchlist, THE Frontend SHALL subscribe to live quotes via WebSocket
2. WHEN live tick is received, THE Frontend SHALL update watchlist prices in real-time
3. WHEN user opens chart, THE Frontend SHALL subscribe to symbol ticks for chart updates
4. THE Frontend SHALL handle WebSocket reconnection automatically on disconnect
5. WHEN user switches symbols, THE Frontend SHALL unsubscribe from old symbol and subscribe to new
6. THE Frontend SHALL support multiple subscription modes: LTP, Quote, Full depth

### Requirement 3: Historical Chart Data Integration

**User Story:** As a trader, I want to view historical price charts with multiple timeframes, so that I can analyze price movements.

#### Acceptance Criteria

1. WHEN user opens chart, THE Frontend SHALL fetch historical OHLC data from backend
2. THE Frontend SHALL support all intervals: 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 1d, 1w, 1M
3. WHEN user changes interval, THE Frontend SHALL fetch data for new interval
4. THE Frontend SHALL cache historical data to reduce API calls
5. WHEN new candle completes, THE Frontend SHALL fetch only missing candles
6. THE Frontend SHALL handle timezone conversion for IST display

### Requirement 4: Option Chain Integration

**User Story:** As an options trader, I want to view option chain with live prices and Greeks, so that I can analyze and select options.

#### Acceptance Criteria

1. WHEN user opens option chain, THE Frontend SHALL fetch option chain data from backend
2. THE Frontend SHALL display all strikes with CE and PE data
3. THE Frontend SHALL highlight ATM strike based on underlying LTP
4. WHEN user selects expiry, THE Frontend SHALL fetch data for that expiry
5. THE Frontend SHALL fetch and display Greeks for each option
6. THE Frontend SHALL subscribe to live updates for option prices via WebSocket
7. THE Frontend SHALL support batch Greeks calculation for performance

### Requirement 5: Symbol Search Integration

**User Story:** As a trader, I want to search for symbols across all exchanges, so that I can find instruments to trade.

#### Acceptance Criteria

1. WHEN user types in search box, THE Frontend SHALL call backend search API with query
2. THE Frontend SHALL display search results with symbol, name, exchange, instrument type
3. THE Frontend SHALL support fuzzy matching for partial queries
4. THE Frontend SHALL search across all exchanges: NSE, BSE, NFO, BFO, MCX
5. WHEN user selects symbol, THE Frontend SHALL add it to watchlist or open chart

### Requirement 6: Market Timings and Holidays Integration

**User Story:** As a trader, I want to see market timings and holidays, so that I can plan my trading.

#### Acceptance Criteria

1. THE Frontend SHALL fetch market timings from backend for current date
2. THE Frontend SHALL display market open/closed status in UI
3. THE Frontend SHALL fetch holiday list from backend
4. THE Frontend SHALL show holiday indicator on chart for non-trading days
5. THE Frontend SHALL handle special trading sessions (Muhurat trading)

### Requirement 7: Order Placement Integration

**User Story:** As a trader, I want to place orders from the dashboard, so that I can execute trades.

#### Acceptance Criteria

1. WHEN user places order, THE Frontend SHALL call backend order placement API
2. THE Frontend SHALL support all order types: Market, Limit, SL, SL-M
3. THE Frontend SHALL support all product types: MIS, CNC, NRML
4. THE Frontend SHALL validate order parameters before submission
5. IF order placement succeeds, THEN THE Frontend SHALL show success message and refresh order book
6. IF order placement fails, THEN THE Frontend SHALL show error message with reason

### Requirement 8: Order Modification and Cancellation

**User Story:** As a trader, I want to modify or cancel pending orders, so that I can manage my orders.

#### Acceptance Criteria

1. WHEN user modifies order, THE Frontend SHALL call backend order modification API
2. WHEN user cancels order, THE Frontend SHALL call backend order cancellation API
3. THE Frontend SHALL support modifying price, quantity, trigger price
4. IF modification succeeds, THEN THE Frontend SHALL refresh order book
5. IF cancellation succeeds, THEN THE Frontend SHALL remove order from order book

### Requirement 9: Position Management Integration

**User Story:** As a trader, I want to exit positions from the dashboard, so that I can close trades.

#### Acceptance Criteria

1. WHEN user exits position, THE Frontend SHALL call backend position exit API
2. THE Frontend SHALL support full exit and partial exit
3. THE Frontend SHALL calculate exit quantity based on position size
4. IF exit succeeds, THEN THE Frontend SHALL refresh position book
5. THE Frontend SHALL show live P&L for each position

### Requirement 10: WebSocket Connection Management

**User Story:** As a system, I want to manage WebSocket connections efficiently, so that real-time data flows smoothly.

#### Acceptance Criteria

1. THE Frontend SHALL establish single WebSocket connection to backend
2. THE Frontend SHALL authenticate WebSocket connection with API key
3. THE Frontend SHALL handle automatic reconnection on disconnect
4. THE Frontend SHALL implement heartbeat/ping-pong to keep connection alive
5. WHEN connection drops, THE Frontend SHALL show connection status indicator
6. WHEN connection restores, THE Frontend SHALL resubscribe to all symbols

### Requirement 11: Error Handling and User Feedback

**User Story:** As a trader, I want to see clear error messages and loading states, so that I know what's happening.

#### Acceptance Criteria

1. WHEN API call is in progress, THE Frontend SHALL show loading indicator
2. IF API call fails, THEN THE Frontend SHALL show error message with reason
3. THE Frontend SHALL handle network errors gracefully
4. THE Frontend SHALL handle broker API errors with user-friendly messages
5. THE Frontend SHALL show toast notifications for important events

### Requirement 12: Authentication and Session Management

**User Story:** As a trader, I want to login to AngelOne broker, so that I can access my account.

#### Acceptance Criteria

1. WHEN user enters credentials, THE Frontend SHALL call backend login API
2. THE Frontend SHALL store API key in localStorage after successful login
3. THE Frontend SHALL validate API key on page load
4. IF API key is invalid, THEN THE Frontend SHALL redirect to login page
5. THE Frontend SHALL handle token refresh automatically
6. WHEN user logs out, THE Frontend SHALL clear API key and redirect to login

### Requirement 13: Data Caching and Performance

**User Story:** As a system, I want to cache data efficiently, so that the dashboard loads fast.

#### Acceptance Criteria

1. THE Frontend SHALL cache historical chart data in memory
2. THE Frontend SHALL cache option chain data with 5-minute TTL
3. THE Frontend SHALL cache symbol master data with 24-hour TTL
4. THE Frontend SHALL use stale-while-revalidate pattern for quotes
5. THE Frontend SHALL limit cache size to prevent memory issues

### Requirement 14: Indicator and Drawing Tools Integration

**User Story:** As a trader, I want to use indicators and drawing tools on charts, so that I can perform technical analysis.

#### Acceptance Criteria

1. THE Frontend SHALL support all built-in indicators: MA, EMA, RSI, MACD, Bollinger Bands
2. THE Frontend SHALL support custom indicators with backend data
3. THE Frontend SHALL support drawing tools: trendlines, horizontal lines, rectangles
4. THE Frontend SHALL persist drawings to localStorage
5. THE Frontend SHALL support chart templates with saved indicators

### Requirement 15: Alert System Integration

**User Story:** As a trader, I want to set price alerts, so that I get notified when price reaches target.

#### Acceptance Criteria

1. WHEN user creates alert, THE Frontend SHALL call backend alert creation API
2. THE Frontend SHALL support price alerts: above, below, crossing
3. WHEN alert triggers, THE Frontend SHALL show notification
4. THE Frontend SHALL fetch and display all active alerts
5. WHEN user deletes alert, THE Frontend SHALL call backend alert deletion API

### Requirement 16: Multi-Symbol Support

**User Story:** As a trader, I want to monitor multiple symbols simultaneously, so that I can track multiple markets.

#### Acceptance Criteria

1. THE Frontend SHALL support multiple symbols in watchlist
2. THE Frontend SHALL support multiple chart windows
3. THE Frontend SHALL subscribe to all visible symbols via WebSocket
4. THE Frontend SHALL unsubscribe from symbols when removed from watchlist
5. THE Frontend SHALL handle subscription limits gracefully

### Requirement 17: Broker-Specific Features

**User Story:** As a trader, I want to use AngelOne-specific features, so that I can leverage broker capabilities.

#### Acceptance Criteria

1. THE Frontend SHALL support AngelOne order types and product types
2. THE Frontend SHALL display AngelOne-specific error codes with translations
3. THE Frontend SHALL support AngelOne WebSocket feed format
4. THE Frontend SHALL handle AngelOne rate limits gracefully
5. THE Frontend SHALL support AngelOne margin calculator

### Requirement 18: Settings and Configuration

**User Story:** As a trader, I want to configure backend URL and settings, so that I can connect to my backend.

#### Acceptance Criteria

1. THE Frontend SHALL provide settings dialog for backend URL configuration
2. THE Frontend SHALL validate backend URL before saving
3. THE Frontend SHALL support WebSocket URL configuration
4. THE Frontend SHALL test connection to backend on settings save
5. THE Frontend SHALL persist settings to localStorage

### Requirement 19: Responsive Design and Mobile Support

**User Story:** As a trader, I want to use the dashboard on mobile devices, so that I can trade on the go.

#### Acceptance Criteria

1. THE Frontend SHALL be responsive and work on mobile devices
2. THE Frontend SHALL adapt layout for small screens
3. THE Frontend SHALL support touch gestures for chart interaction
4. THE Frontend SHALL optimize API calls for mobile networks
5. THE Frontend SHALL support mobile-friendly order placement

### Requirement 20: Data Consistency and Synchronization

**User Story:** As a system, I want to keep data consistent across components, so that users see accurate information.

#### Acceptance Criteria

1. WHEN position is updated, THE Frontend SHALL refresh position book and account funds
2. WHEN order is placed, THE Frontend SHALL refresh order book and available margin
3. WHEN trade executes, THE Frontend SHALL refresh trade book and position book
4. THE Frontend SHALL use event-driven updates for data synchronization
5. THE Frontend SHALL handle race conditions in data updates

