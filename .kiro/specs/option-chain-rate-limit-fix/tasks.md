# Implementation Plan: Option Chain Rate Limit Fix

## Overview

This implementation plan converts the option chain rate limit fix design into actionable coding tasks. The approach focuses on implementing the Instrument Master File solution to eliminate rate limit errors by reducing API calls from 100+ to 2-3 per option chain request.

The implementation follows this sequence:
1. Add database indexes for optimization
2. Implement instrument master download and parsing
3. Implement database storage with bulk insert
4. Rewrite option chain logic to use database queries
5. Add health check and manual refresh endpoints
6. Implement scheduled daily refresh
7. Add comprehensive testing

## Tasks

- [x] 1. Add database indexes for option chain queries
  - Modify `InstrumentMaster` model in `backend/app/models/database.py`
  - Add composite index: `idx_option_chain_query` on (symbol, exchange, expiry, option_type, strike)
  - Add index: `idx_instrument_expiry` on (expiry)
  - Add index: `idx_instrument_option_type` on (option_type)
  - Generate and run Alembic migration to create indexes
  - _Requirements: 2.2, 7.3_

- [ ] 2. Implement instrument master download in Symbol Service
  - [x] 2.1 Add `download_instrument_master()` method to `SymbolService` class
    - Download JSON from Angel One URL (from endpoints.py)
    - Implement retry logic with exponential backoff (3 attempts: 1s, 2s, 4s)
    - Return list of raw instrument dictionaries
    - Handle network errors and timeouts gracefully
    - _Requirements: 1.1, 1.3_
  
  - [ ] 2.2 Write property test for download retry logic
    - **Property 2: Download Retry with Exponential Backoff**
    - **Validates: Requirements 1.3**
  
  - [x] 2.3 Add `parse_instrument_record()` method to `SymbolService` class
    - Parse single instrument dictionary from JSON
    - Validate required fields (symbol, token, exchange)
    - Extract option_type from symbol (CE/PE)
    - Return `InstrumentMaster` model instance or None
    - _Requirements: 1.2, 1.5_
  
  - [ ] 2.4 Write property test for JSON validation
    - **Property 3: JSON Validation**
    - **Validates: Requirements 1.5**
  
  - [ ] 2.5 Write property test for parsing and storage
    - **Property 1: Instrument Master Parsing and Storage**
    - **Validates: Requirements 1.2, 2.1**

- [ ] 3. Implement bulk storage in Symbol Service
  - [x] 3.1 Add `store_instruments_bulk()` method to `SymbolService` class
    - Clear existing instrument_master table records
    - Use bulk insert for performance (SQLAlchemy bulk_insert_mappings)
    - Wrap in database transaction for atomicity
    - Log count of instruments stored
    - Return count of successful inserts
    - _Requirements: 2.1, 2.3, 2.4, 2.5_
  
  - [ ] 3.2 Write property test for idempotent storage
    - **Property 4: Idempotent Storage**
    - **Validates: Requirements 2.3**
  
  - [ ] 3.3 Write property test for atomic transactions
    - **Property 5: Atomic Transaction Updates**
    - **Validates: Requirements 2.4**

- [ ] 4. Implement database query methods in Symbol Service
  - [x] 4.1 Add `query_options_by_expiry()` method to `SymbolService` class
    - Query instruments filtered by underlying name, exchange, expiry
    - Filter for option_type in ["CE", "PE"]
    - Order results by strike price ascending
    - Return list of `InstrumentMaster` instances
    - Use indexed query for performance
    - _Requirements: 3.2, 3.3, 3.4_
  
  - [ ] 4.2 Write property test for complete option chain results
    - **Property 7: Complete Option Chain Results**
    - **Validates: Requirements 3.2, 3.3, 3.4**
  
  - [x] 4.3 Add `get_instrument_health()` method to `SymbolService` class
    - Check if instrument data exists in database
    - Get count of instruments
    - Get last updated timestamp
    - Check if data is stale (>48 hours)
    - Return health status dictionary
    - _Requirements: 6.3_
  
  - [ ] 4.4 Write property test for health check accuracy
    - **Property 13: Health Check Accuracy**
    - **Validates: Requirements 6.2, 6.3**

- [ ] 5. Update Symbol Service refresh_master method
  - [x] 5.1 Modify `refresh_master()` method in `SymbolService` class
    - Call `download_instrument_master()` instead of broker method
    - Call `parse_instrument_record()` for each record
    - Call `store_instruments_bulk()` with parsed instruments
    - Handle download failures gracefully (log and continue)
    - Update last refresh timestamp in cache
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.1_
  
  - [ ] 5.2 Write property test for refresh process consistency
    - **Property 11: Refresh Process Consistency**
    - **Validates: Requirements 5.3**

- [ ] 6. Rewrite get_option_chain in Angel One Adapter
  - [x] 6.1 Modify `get_option_chain()` method in `AngelOneAdapter` class
    - Remove all `search_symbols()` API calls
    - Query database using `symbol_service.query_options_by_expiry()`
    - Extract tokens from database results
    - Group tokens into batches of 50
    - Call `get_quotes_batch()` for each batch (existing method)
    - Combine batch results into option chain response
    - _Requirements: 3.1, 4.1, 4.2, 4.3, 4.4_
  
  - [ ] 6.2 Write property test for database query instead of API
    - **Property 6: Database Query Instead of API**
    - **Validates: Requirements 3.1**
  
  - [ ] 6.3 Write property test for batch API call count
    - **Property 8: Batch Quote API Call Count**
    - **Validates: Requirements 4.1, 4.2**
  
  - [ ] 6.4 Write property test for batch result completeness
    - **Property 9: Batch Result Completeness**
    - **Validates: Requirements 4.4**
  
  - [ ] 6.5 Write property test for batch retry logic
    - **Property 10: Batch Retry Logic**
    - **Validates: Requirements 4.5**

- [ ] 7. Update startup script for instrument master initialization
  - [x] 7.1 Modify `init_instrument_master()` function in `backend/scripts/startup.py`
    - Create broker adapter instance (use factory)
    - Create symbol service instance with database session
    - Call `symbol_service.refresh_master(force=True)`
    - Implement retry logic (3 attempts with exponential backoff)
    - Log detailed progress and errors
    - Continue startup even if all retries fail
    - _Requirements: 1.1, 1.3, 1.4, 6.1_
  
  - [ ] 7.2 Write unit test for startup initialization
    - Test successful initialization
    - Test failure handling and startup continuation
    - _Requirements: 1.1, 1.4, 6.1_

- [x] 8. Checkpoint - Verify core functionality
  - Run all tests to ensure instrument master download, storage, and querying work correctly
  - Manually test option chain endpoint to verify API call reduction
  - Check database for proper indexes and data
  - Ensure all tests pass, ask the user if questions arise

- [ ] 9. Add health check and manual refresh endpoints
  - [ ] 9.1 Create health check endpoint in `backend/app/api/v1/health.py`
    - Add GET `/api/health/instruments` endpoint
    - Call `symbol_service.get_instrument_health()`
    - Return JSON with availability, count, last_updated, is_stale
    - _Requirements: 6.3_
  
  - [ ] 9.2 Create manual refresh endpoint in `backend/app/api/v1/admin.py`
    - Add POST `/api/admin/refresh-instruments` endpoint
    - Require admin authentication (check API key or role)
    - Call `symbol_service.refresh_master(force=True)`
    - Return JSON with success status and count
    - _Requirements: 6.5_
  
  - [ ] 9.3 Write unit tests for health and refresh endpoints
    - Test health check with available data
    - Test health check with unavailable data
    - Test manual refresh success
    - Test manual refresh failure
    - _Requirements: 6.3, 6.5_

- [ ] 10. Implement scheduled daily refresh
  - [ ] 10.1 Add APScheduler dependency to requirements.txt
    - Add `apscheduler==3.10.4` to requirements
    - _Requirements: 5.1_
  
  - [ ] 10.2 Create scheduler module in `backend/app/services/scheduler.py`
    - Initialize APScheduler with AsyncIOScheduler
    - Add `schedule_daily_refresh()` function
    - Schedule refresh at 7:00 AM IST daily
    - Call `symbol_service.refresh_master()` on schedule
    - Handle failures gracefully (log and retain existing data)
    - _Requirements: 5.1, 5.2, 5.3, 5.4_
  
  - [ ] 10.3 Initialize scheduler in main.py startup event
    - Import and call `schedule_daily_refresh()` in FastAPI startup
    - Ensure scheduler starts with application
    - Add shutdown handler to stop scheduler gracefully
    - _Requirements: 5.1_
  
  - [ ] 10.4 Write unit tests for scheduler
    - Test scheduler configuration
    - Test scheduled task execution
    - Test failure handling during refresh
    - _Requirements: 5.1, 5.2, 5.4_
  
  - [ ] 10.5 Write property test for concurrent request safety
    - **Property 12: Concurrent Request Safety**
    - **Validates: Requirements 5.5**

- [ ] 11. Add caching for instrument lookups
  - [ ] 11.1 Add in-memory cache to `SymbolService` class
    - Use TTLCache from cachetools library (5 minute TTL)
    - Cache `get_symbol_token()` results
    - Cache `query_options_by_expiry()` results
    - Invalidate cache on refresh
    - _Requirements: 7.4_
  
  - [ ] 11.2 Write property test for cache consistency
    - **Property 14: Cache Consistency**
    - **Validates: Requirements 7.4**

- [ ] 12. Add comprehensive error handling
  - [ ] 12.1 Add error handling for download failures
    - Catch network errors and timeouts
    - Log detailed error information
    - Return descriptive error messages
    - _Requirements: 1.3, 1.4_
  
  - [ ] 12.2 Add error handling for parse failures
    - Validate JSON structure
    - Skip invalid records with logging
    - Return count of successful and failed records
    - _Requirements: 1.5_
  
  - [ ] 12.3 Add error handling for database failures
    - Wrap operations in transactions
    - Rollback on errors
    - Retry once after delay
    - _Requirements: 2.4_
  
  - [ ] 12.4 Add error handling for option chain queries
    - Check if instrument data exists
    - Return descriptive error if unavailable
    - Return empty chain if no matches found
    - _Requirements: 3.5, 6.2_
  
  - [ ] 12.5 Write unit tests for error scenarios
    - Test download failure handling
    - Test parse error handling
    - Test database error handling
    - Test option chain unavailable error
    - _Requirements: 1.3, 1.4, 1.5, 2.4, 3.5, 6.2_

- [ ] 13. Final checkpoint - Integration testing
  - Run full integration test suite
  - Verify end-to-end option chain flow works
  - Verify API call count is reduced from 100+ to 2-3
  - Verify no search API calls are made
  - Test refresh flow and failure recovery
  - Ensure all tests pass, ask the user if questions arise

- [ ] 14. Update documentation
  - [ ] 14.1 Add API documentation for new endpoints
    - Document `/api/health/instruments` endpoint
    - Document `/api/admin/refresh-instruments` endpoint
    - Add examples and response schemas
  
  - [ ] 14.2 Update deployment documentation
    - Document instrument master initialization on startup
    - Document scheduled refresh configuration
    - Add troubleshooting guide for common issues
  
  - [ ] 14.3 Add monitoring and alerting recommendations
    - Document metrics to monitor (refresh success rate, data staleness)
    - Recommend alerts for stale data (>48 hours)
    - Document API call reduction verification

## Notes

- All tasks are required for comprehensive implementation
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation of functionality
- Property tests validate universal correctness properties with 100+ iterations
- Unit tests validate specific examples and edge cases
- The implementation reduces API calls by 97% (from 100+ to 2-3 per option chain request)
