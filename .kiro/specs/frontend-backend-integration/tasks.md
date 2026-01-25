# Implementation Plan: Frontend-Backend Integration

## Overview

Yeh implementation plan frontend dashboard ko AngelOne backend se systematically connect karega. Plan 5 phases mein divided hai: Service Layer, WebSocket, Components, Authentication, aur Testing. Har task incremental hai aur previous tasks pe build karta hai.

## Tasks

- [x] 1. Service Layer Refactoring
  - [x] 1.1 Create unified API service
    - Create `frontend/src/services/apiService.js` with `callBackendAPI()` function
    - Add error handling and response validation
    - Add request/response logging for debugging
    - _Requirements: 11.1, 11.2_

  - [x] 1.2 Update Account Service
    - Update `frontend/src/services/accountService.js` to use `callBackendAPI()`
    - Update `getFunds()`, `getPositionBook()`, `getOrderBook()`, `getTradeBook()`, `getHoldings()`
    - Add `placeOrder()`, `modifyOrder()`, `cancelOrder()`, `closePosition()` functions
    - Remove any direct AngelOne API calls
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 7.1, 8.1, 8.2, 9.1_

  - [x] 1.3 Create Market Data Service
    - Create `frontend/src/services/marketDataService.js`
    - Implement `getHistoricalData()` for OHLC data
    - Implement `getQuote()` and `getBatchQuotes()` for live quotes
    - Implement `searchSymbols()` for symbol search
    - Add caching for historical data
    - _Requirements: 3.1, 3.2, 3.4, 5.1_

  - [x] 1.4 Update Option Chain Service
    - Update `frontend/src/services/optionChain.js` to use backend APIs
    - Update `getOptionChain()` to call `/api/v1/optionchain`
    - Update `getAvailableExpiries()` to call `/api/v1/expiry`
    - Update `getOptionGreeks()` and `getBatchOptionGreeks()` to call `/api/v1/greeks`
    - Keep existing cache logic
    - _Requirements: 4.1, 4.4, 4.5, 4.7_

  - [x] 1.5 Update Market Service
    - Verify `frontend/src/services/marketService.js` uses backend APIs
    - Ensure `getMarketTimings()` and `getMarketHolidays()` work correctly
    - Test market open/closed status
    - _Requirements: 6.1, 6.2, 6.3_

- [x] 2. Checkpoint - Service Layer Complete
  - Test all service functions with backend
  - Verify error handling works
  - Check caching behavior
  - Ask user if questions arise

- [x] 3. WebSocket Integration
  - [x] 3.1 Create WebSocket Manager
    - Create `frontend/src/services/websocketManager.js`
    - Implement `WebSocketManager` class with connect/disconnect
    - Implement subscribe/unsubscribe with callback management
    - Implement authentication with API key
    - _Requirements: 10.1, 10.2_

  - [x] 3.2 Implement reconnection logic
    - Add automatic reconnection with exponential backoff
    - Implement resubscription after reconnect
    - Add connection status tracking
    - _Requirements: 2.4, 10.3, 10.6_

  - [x] 3.3 Implement heartbeat mechanism
    - Add ping/pong heartbeat every 30 seconds
    - Handle ping messages from backend
    - Detect connection timeout
    - _Requirements: 10.4_

  - [x] 3.4 Add message handling
    - Handle 'auth' messages
    - Handle 'market_data' messages
    - Route ticks to registered callbacks
    - Handle 'ping' messages
    - _Requirements: 2.1, 2.2_

  - [x] 3.5 Create singleton instance
    - Export `wsManager` singleton
    - Add initialization on app load
    - Add cleanup on app unload
    - _Requirements: 10.1_

- [x] 4. Checkpoint - WebSocket Complete
  - Test WebSocket connection
  - Test subscription/unsubscription
  - Test reconnection logic
  - Test message routing
  - Ask user if questions arise

- [x] 5. Component Integration - Chart
  - [x] 5.1 Update Chart Component historical data fetching
    - Update `frontend/src/components/Chart/ChartComponent.jsx`
    - Use `getHistoricalData()` from marketDataService
    - Handle loading states
    - Handle errors with fallback
    - _Requirements: 3.1, 3.2_

  - [x] 5.2 Add WebSocket live updates to Chart
    - Subscribe to symbol ticks on mount
    - Update last candle with live ticks
    - Create new candle when interval changes
    - Unsubscribe on unmount
    - _Requirements: 2.1, 2.2, 2.5_

  - [x] 5.3 Handle interval changes
    - Fetch new data when interval changes
    - Clear old data before loading new
    - Maintain WebSocket subscription
    - _Requirements: 3.2, 3.3_

  - [x] 5.4 Add timezone handling
    - Convert timestamps to IST for display
    - Handle market session boundaries
    - _Requirements: 3.6, 6.1_

- [x] 6. Component Integration - Watchlist
  - [x] 6.1 Update Watchlist Component
    - Update `frontend/src/components/Watchlist/Watchlist.jsx`
    - Use `getQuote()` for initial quotes
    - Subscribe to live updates via WebSocket
    - Update quotes in real-time
    - _Requirements: 2.1, 2.2_

  - [x] 6.2 Implement add/remove symbol
    - Add symbol with initial quote fetch
    - Subscribe to WebSocket on add
    - Unsubscribe on remove
    - Persist watchlist to localStorage
    - _Requirements: 2.1, 2.5, 16.4_

  - [x] 6.3 Add multi-symbol support
    - Handle multiple symbols simultaneously
    - Optimize WebSocket subscriptions
    - Handle subscription limits
    - _Requirements: 16.1, 16.3_

- [x] 7. Component Integration - Account Panel
  - [x] 7.1 Update Account Panel Component
    - Update `frontend/src/components/AccountPanel/AccountPanel.jsx`
    - Use updated accountService functions
    - Implement auto-refresh every 5 seconds
    - Handle loading and error states
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6_

  - [x] 7.2 Add live P&L updates for positions
    - Subscribe to position symbols via WebSocket
    - Calculate live P&L with current prices
    - Update position table in real-time
    - _Requirements: 1.2, 9.5_

  - [x] 7.3 Implement order actions
    - Add cancel order button with handler
    - Add modify order dialog
    - Show success/error toasts
    - Refresh order book after actions
    - _Requirements: 8.1, 8.2, 8.4, 8.5_

  - [x] 7.4 Implement position exit
    - Add exit position button
    - Show exit confirmation dialog
    - Call `closePosition()` API
    - Refresh position book after exit
    - _Requirements: 9.1, 9.2, 9.4_

- [x] 8. Component Integration - Option Chain
  - [x] 8.1 Update Option Chain Component
    - Update `frontend/src/components/OptionChainModal/OptionChainModal.jsx`
    - Use updated optionChainService
    - Fetch option chain on open
    - Handle loading and error states
    - _Requirements: 4.1, 4.2_

  - [x] 8.2 Add expiry selection
    - Fetch available expiries
    - Show expiry tabs
    - Fetch chain for selected expiry
    - _Requirements: 4.4_

  - [x] 8.3 Add Greeks display
    - Fetch Greeks for visible options
    - Use batch API for performance
    - Display Delta, Gamma, Theta, Vega, IV
    - _Requirements: 4.5, 4.7_

  - [x] 8.4 Add live price updates
    - Subscribe to option symbols via WebSocket
    - Update option prices in real-time
    - Update ATM strike dynamically
    - _Requirements: 4.6_

- [x] 9. Checkpoint - Components Complete
  - Test all components with backend
  - Verify live updates work
  - Check error handling
  - Ask user if questions arise

- [x] 10. Authentication Integration
  - [x] 10.1 Create Authentication Service
    - Create `frontend/src/services/authService.js`
    - Implement `login()` function
    - Implement `logout()` function
    - Implement `isAuthenticated()` check
    - Implement `validateApiKey()` function
    - _Requirements: 12.1, 12.2, 12.3, 12.6_

  - [x] 10.2 Update Login Component
    - Update `frontend/src/components/BrokerLogin/BrokerLogin.jsx`
    - Use `authService.login()` for authentication
    - Store API key in localStorage on success
    - Connect WebSocket after login
    - Redirect to dashboard on success
    - _Requirements: 12.1, 12.2_

  - [x] 10.3 Add authentication guard
    - Create `AuthGuard` component
    - Check authentication on app load
    - Redirect to login if not authenticated
    - Validate API key with backend
    - _Requirements: 12.3, 12.4_

  - [x] 10.4 Add logout functionality
    - Add logout button in UI
    - Call `authService.logout()`
    - Clear API key from localStorage
    - Disconnect WebSocket
    - Redirect to login page
    - _Requirements: 12.6_

  - [x] 10.5 Handle token refresh
    - Detect 401 errors
    - Attempt token refresh
    - Redirect to login if refresh fails
    - _Requirements: 12.5_

- [x] 11. Error Handling and User Feedback
  - [x] 11.1 Create Error Handler Utility
    - Create `frontend/src/utils/errorHandler.js`
    - Implement `handleApiError()` function
    - Implement `handleWebSocketError()` function
    - Implement `handleNetworkError()` function
    - Map error codes to user-friendly messages
    - _Requirements: 11.2, 11.4_

  - [x] 11.2 Add Toast Notification Service
    - Install `react-toastify` if not present
    - Create `frontend/src/services/toastService.js`
    - Implement success, error, info, warning toasts
    - Configure toast position and duration
    - _Requirements: 11.1_

  - [x] 11.3 Add loading indicators
    - Add loading spinners to all components
    - Show loading during API calls
    - Show skeleton loaders for tables
    - _Requirements: 11.1_

  - [x] 11.4 Add connection status indicator
    - Show WebSocket connection status in UI
    - Show "Connecting...", "Connected", "Disconnected"
    - Show reconnection attempts
    - _Requirements: 10.5_

- [x] 12. Settings and Configuration
  - [x] 12.1 Update Settings Component
    - Update `frontend/src/components/Settings/SettingsPopup.jsx`
    - Add backend URL configuration
    - Add WebSocket URL configuration
    - Add test connection button
    - _Requirements: 18.1, 18.2, 18.3_

  - [x] 12.2 Add connection testing
    - Implement `testConnection()` function
    - Call `/api/v1/ping` to test backend
    - Show success/error message
    - Save settings only if test passes
    - _Requirements: 18.4_

  - [x] 12.3 Persist settings
    - Save settings to localStorage
    - Load settings on app start
    - Apply settings to apiConfig
    - _Requirements: 18.5_

- [x] 13. Data Consistency and Synchronization
  - [x] 13.1 Implement event-driven updates
    - Create event emitter for data changes
    - Emit events on order placement, position exit
    - Listen to events in relevant components
    - Refresh data on events
    - _Requirements: 20.1, 20.2, 20.3, 20.4_

  - [x] 13.2 Add data refresh coordination
    - Coordinate refreshes across components
    - Avoid duplicate API calls
    - Use shared state for common data
    - _Requirements: 20.5_

- [x] 14. Checkpoint - Integration Complete
  - Test full application flow
  - Test all features end-to-end
  - Verify no regressions
  - Ask user if questions arise

- [ ] 15. Testing and Quality Assurance
  - [ ] 15.1 Write unit tests for services
    - Test apiService with mocked fetch
    - Test accountService functions
    - Test marketDataService functions
    - Test optionChainService functions
    - Test authService functions
    - _Requirements: All_

  - [ ] 15.2 Write unit tests for WebSocket Manager
    - Test connection/disconnection
    - Test subscribe/unsubscribe
    - Test message handling
    - Test reconnection logic
    - _Requirements: 2.4, 10.3, 10.6_

  - [ ] 15.3 Write component tests
    - Test Chart component
    - Test Watchlist component
    - Test Account Panel component
    - Test Option Chain component
    - Test Login component
    - _Requirements: All_

  - [ ] 15.4 Write integration tests
    - Test authentication flow
    - Test WebSocket connection and data flow
    - Test order placement flow
    - Test position exit flow
    - _Requirements: All_

  - [ ] 15.5 Write property-based tests
    - Test WebSocket subscription consistency
    - Test cache TTL expiration
    - Test data transformation integrity
    - Test order validation
    - Test position P&L calculation
    - _Requirements: All_

- [ ] 16. Performance Optimization
  - [ ] 16.1 Implement request debouncing
    - Debounce symbol search
    - Debounce chart interval changes
    - Avoid rapid API calls
    - _Requirements: 13.1_

  - [ ] 16.2 Optimize WebSocket subscriptions
    - Batch subscribe/unsubscribe requests
    - Avoid duplicate subscriptions
    - Unsubscribe from invisible symbols
    - _Requirements: 16.3, 16.4_

  - [ ] 16.3 Implement cache eviction
    - Limit cache size for option chain
    - Limit cache size for historical data
    - Use LRU eviction strategy
    - _Requirements: 13.5_

  - [ ] 16.4 Add lazy loading
    - Lazy load chart indicators
    - Lazy load option chain Greeks
    - Load data on demand
    - _Requirements: 13.1_

- [ ] 17. Mobile Responsiveness
  - [ ] 17.1 Test on mobile devices
    - Test on iOS Safari
    - Test on Android Chrome
    - Test touch gestures
    - _Requirements: 19.1, 19.3_

  - [ ] 17.2 Optimize for mobile
    - Adapt layout for small screens
    - Optimize API calls for mobile networks
    - Add mobile-friendly order placement
    - _Requirements: 19.2, 19.4, 19.5_

- [ ] 18. Final Testing and Bug Fixes
  - [ ] 18.1 End-to-end testing
    - Test complete user journey
    - Test all features
    - Test error scenarios
    - _Requirements: All_

  - [ ] 18.2 Fix bugs found during testing
    - Document bugs
    - Fix critical bugs
    - Fix non-critical bugs
    - _Requirements: All_

  - [ ] 18.3 Performance testing
    - Test with multiple symbols
    - Test with high-frequency updates
    - Measure memory usage
    - Optimize if needed
    - _Requirements: 13.1, 13.5_

- [ ] 19. Final Checkpoint
  - Run all tests
  - Verify all features work
  - Get user approval
  - Deploy to production

## Notes

- All tasks are required for complete integration
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties
- Focus on maintaining existing functionality while adding backend integration

