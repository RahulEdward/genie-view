# Requirements Document

## Introduction

This specification addresses the critical rate limit issue in the option chain feature. The current implementation makes 100+ individual API calls to Angel One's search endpoint for each option chain request, quickly exceeding the rate limit of 25-30 requests per minute. This renders the option chain feature non-functional.

The solution implements the Instrument Master File approach, where all tradable instruments are downloaded once and stored in the database. This reduces API calls from 100+ to 2-3 per option chain request by querying the database for instrument tokens and only making batch quote requests.

## Glossary

- **Instrument_Master_File**: A comprehensive JSON file provided by Angel One containing all tradable instruments with their tokens, symbols, exchanges, expiry dates, strikes, and option types
- **Option_Chain_Service**: The backend service responsible for fetching and formatting option chain data
- **Symbol_Service**: The backend service responsible for instrument symbol lookups and token resolution
- **Instrument_Database**: The PostgreSQL database table storing instrument master data with indexes for efficient querying
- **Batch_Quote_Request**: An API call that fetches quotes for up to 50 instruments simultaneously
- **Rate_Limit**: Angel One API restriction of approximately 25-30 requests per minute
- **Startup_Script**: The initialization script that runs when the backend application starts

## Requirements

### Requirement 1: Download Instrument Master File

**User Story:** As a system administrator, I want the instrument master file to be downloaded automatically on startup, so that the application has access to all tradable instruments without making repeated API calls.

#### Acceptance Criteria

1. WHEN the backend application starts, THE Startup_Script SHALL download the instrument master file from Angel One's public URL
2. WHEN the download succeeds, THE Symbol_Service SHALL parse the JSON file and extract all instrument records
3. IF the download fails, THEN THE Startup_Script SHALL log the error and retry up to 3 times with exponential backoff
4. WHEN all retry attempts fail, THEN THE Startup_Script SHALL continue startup but log a critical warning
5. THE Symbol_Service SHALL validate that the downloaded file contains valid JSON with expected fields (symbol, token, exchange, expiry, strike, option_type)

### Requirement 2: Store Instruments in Database

**User Story:** As a developer, I want instruments stored in a database with proper indexes, so that I can query them efficiently without making API calls.

#### Acceptance Criteria

1. WHEN instrument records are parsed, THE Symbol_Service SHALL store them in the Instrument_Database using bulk insert operations
2. THE Instrument_Database SHALL maintain indexes on symbol, exchange, expiry, strike, and option_type fields
3. WHEN storing new instruments, THE Symbol_Service SHALL clear existing records before inserting to prevent duplicates
4. THE Symbol_Service SHALL use database transactions to ensure atomic updates
5. WHEN the database insert completes, THE Symbol_Service SHALL log the total count of instruments stored

### Requirement 3: Query Instruments from Database

**User Story:** As a backend service, I want to query instrument tokens from the database, so that I can avoid making search API calls that cause rate limit errors.

#### Acceptance Criteria

1. WHEN the Option_Chain_Service needs instrument tokens, THE Symbol_Service SHALL query the Instrument_Database instead of calling the search API
2. THE Symbol_Service SHALL filter instruments by symbol, exchange, expiry date, and option type using indexed queries
3. WHEN querying for option chains, THE Symbol_Service SHALL return all matching call and put options for the specified expiry
4. THE Symbol_Service SHALL return results sorted by strike price in ascending order
5. IF no instruments match the query criteria, THEN THE Symbol_Service SHALL return an empty list without making API calls

### Requirement 4: Implement Batch Quote Requests

**User Story:** As a backend service, I want to fetch quotes in batches of 50 instruments, so that I minimize API calls and avoid rate limits.

#### Acceptance Criteria

1. WHEN the Option_Chain_Service has instrument tokens, THE Option_Chain_Service SHALL group them into batches of 50 tokens maximum
2. THE Option_Chain_Service SHALL make one Batch_Quote_Request per batch to Angel One's quote API
3. WHEN processing 100 option instruments, THE Option_Chain_Service SHALL make exactly 2 API calls instead of 100
4. THE Option_Chain_Service SHALL combine results from all batches into a single response
5. IF a batch request fails, THEN THE Option_Chain_Service SHALL retry that specific batch up to 2 times before failing

### Requirement 5: Periodic Instrument Master Refresh

**User Story:** As a system administrator, I want the instrument master file refreshed daily, so that new instruments and expiries are available without manual intervention.

#### Acceptance Criteria

1. THE Symbol_Service SHALL schedule a daily refresh task to download the latest instrument master file
2. THE Symbol_Service SHALL execute the refresh task at 7:00 AM IST daily (before market open)
3. WHEN the refresh task runs, THE Symbol_Service SHALL download, parse, and store instruments using the same process as startup
4. IF the refresh fails, THEN THE Symbol_Service SHALL retain existing instrument data and log the failure
5. THE Symbol_Service SHALL not interrupt ongoing API requests during the refresh process

### Requirement 6: Graceful Failure Handling

**User Story:** As a developer, I want the system to handle instrument master failures gracefully, so that the application remains functional even when the download fails.

#### Acceptance Criteria

1. IF the instrument master download fails on startup, THEN THE Startup_Script SHALL continue application startup
2. WHEN instrument data is unavailable, THE Option_Chain_Service SHALL return a descriptive error message to the client
3. THE Symbol_Service SHALL expose a health check endpoint that indicates whether instrument data is available
4. WHEN instrument data is stale (older than 48 hours), THE Symbol_Service SHALL log a warning but continue serving requests
5. THE Symbol_Service SHALL provide a manual refresh endpoint for administrators to trigger instrument master download on demand

### Requirement 7: Performance Optimization

**User Story:** As a user, I want option chain requests to complete quickly, so that I can make timely trading decisions.

#### Acceptance Criteria

1. WHEN querying the Instrument_Database, THE Symbol_Service SHALL return results within 50 milliseconds for typical option chain queries
2. THE Option_Chain_Service SHALL complete option chain requests within 2 seconds for chains with up to 100 strikes
3. THE Instrument_Database SHALL use composite indexes to optimize queries filtering by multiple fields simultaneously
4. THE Symbol_Service SHALL cache frequently accessed instrument lookups in memory for 5 minutes
5. WHEN the cache is hit, THE Symbol_Service SHALL return results within 5 milliseconds
