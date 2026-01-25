# Design Document: Option Chain Rate Limit Fix

## Overview

This design addresses the critical rate limit issue in the option chain feature by implementing the Instrument Master File approach. The current implementation makes 100+ individual search API calls for each option chain request, quickly exceeding Angel One's rate limit of 25-30 requests per minute.

The solution downloads a comprehensive instrument master file from Angel One containing all tradable instruments with their tokens. This data is stored in the PostgreSQL database with optimized indexes. Option chain requests will query the database for instrument tokens instead of making API calls, reducing API calls from 100+ to 2-3 per request (only for batch quote fetching).

### Key Benefits

- **Eliminates rate limit errors**: Reduces API calls from 100+ to 2-3 per option chain request
- **Faster response times**: Database queries (50ms) are much faster than API calls (200-500ms each)
- **Better reliability**: No dependency on search API availability during option chain requests
- **Scalability**: Can handle multiple concurrent option chain requests without rate limit concerns

## Architecture

### High-Level Flow

```
Startup:
1. Backend starts → Download instrument master JSON from Angel One
2. Parse JSON → Extract ~200,000 instrument records
3. Store in PostgreSQL → Bulk insert with transaction
4. Create indexes → Optimize for option chain queries

Option Chain Request:
1. Client requests option chain for NIFTY with expiry
2. Query database → Filter by symbol, exchange, expiry, option_type
3. Get instrument tokens → Returns list of matching options
4. Batch quote requests → Group tokens into batches of 50
5. Make 2-3 API calls → Fetch quotes for all options
6. Return formatted response → Combine data and send to client

Daily Refresh:
1. Scheduled task at 7:00 AM IST
2. Download latest instrument master
3. Clear old data and insert new data
4. Update indexes
```

### Component Interaction

```
┌─────────────────┐
│  Startup Script │
│  (startup.py)   │
└────────┬────────┘
         │
         │ calls download_instrument_master()
         ▼
┌─────────────────────────┐
│   Symbol Service        │
│  (symbol.py)            │
│                         │
│  - download_master()    │
│  - parse_instruments()  │
│  - store_in_db()        │
│  - query_instruments()  │
└────────┬────────────────┘
         │
         │ stores/queries
         ▼
┌─────────────────────────┐
│  PostgreSQL Database    │
│  (instrument_master)    │
│                         │
│  Indexes:               │
│  - symbol               │
│  - exchange             │
│  - expiry               │
│  - strike               │
│  - option_type          │
│  - composite indexes    │
└─────────────────────────┘
         ▲
         │ queries
         │
┌────────┴────────────────┐
│  Option Chain Service   │
│  (option.py)            │
│                         │
│  - get_option_chain()   │
│  - batch_quotes()       │
└─────────────────────────┘
         ▲
         │
┌────────┴────────────────┐
│  Angel One Adapter      │
│  (adapter.py)           │
│                         │
│  - get_option_chain()   │
│  - get_quotes_batch()   │
└─────────────────────────┘
```

## Components and Interfaces

### 1. Symbol Service (symbol.py)

**New Methods:**

```python
async def download_instrument_master() -> List[Dict]:
    """
    Download instrument master file from Angel One.
    
    Returns:
        List of instrument dictionaries
    
    Raises:
        BrokerError: If download fails after retries
    """
    pass

async def parse_instrument_record(record: Dict) -> Optional[InstrumentMaster]:
    """
    Parse a single instrument record from the master file.
    
    Args:
        record: Raw instrument dictionary from JSON
    
    Returns:
        InstrumentMaster model instance or None if invalid
    """
    pass

async def store_instruments_bulk(instruments: List[InstrumentMaster]) -> int:
    """
    Store instruments in database using bulk insert.
    
    Args:
        instruments: List of InstrumentMaster instances
    
    Returns:
        Number of instruments stored
    """
    pass

async def query_options_by_expiry(
    underlying: str,
    exchange: str,
    expiry: str
) -> List[InstrumentMaster]:
    """
    Query option instruments for a specific underlying and expiry.
    
    Args:
        underlying: Underlying symbol (e.g., "NIFTY")
        exchange: Exchange code (e.g., "NFO")
        expiry: Expiry date in normalized format (e.g., "30JAN25")
    
    Returns:
        List of matching option instruments sorted by strike
    """
    pass

async def get_instrument_health() -> Dict:
    """
    Check health status of instrument master data.
    
    Returns:
        {
            "available": bool,
            "count": int,
            "last_updated": datetime,
            "is_stale": bool
        }
    """
    pass
```

**Modified Methods:**

```python
async def refresh_master(self, force: bool = False) -> int:
    """
    Refresh instrument master from broker.
    
    Changes:
    - Use download_instrument_master() instead of broker.get_instrument_master()
    - Implement retry logic with exponential backoff
    - Clear existing data before bulk insert
    - Use transactions for atomic updates
    
    Args:
        force: Force refresh even if recently updated
    
    Returns:
        Number of instruments updated
    """
    pass
```

### 2. Angel One Adapter (adapter.py)

**Modified Methods:**

```python
async def get_option_chain(
    self,
    underlying: str,
    exchange: str,
    expiry: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get option chain for an underlying.
    
    Changes:
    - Remove search_symbols() calls
    - Query database for option instruments
    - Only make batch quote API calls
    - Reduce from 100+ API calls to 2-3
    
    Args:
        underlying: Underlying symbol
        exchange: Exchange code
        expiry: Optional expiry date
    
    Returns:
        Option chain data with calls and puts
    """
    pass
```

**New Methods:**

```python
async def get_quotes_batch_optimized(
    self,
    instruments: List[InstrumentMaster]
) -> Dict[str, Quote]:
    """
    Fetch quotes for instruments in optimized batches.
    
    Args:
        instruments: List of InstrumentMaster instances
    
    Returns:
        Dictionary mapping "symbol:exchange" to Quote
    """
    pass
```

### 3. Startup Script (startup.py)

**Modified Functions:**

```python
async def init_instrument_master():
    """
    Initialize instrument master data on startup.
    
    Changes:
    - Add retry logic (3 attempts with exponential backoff)
    - Log detailed progress
    - Continue startup even if download fails
    - Set health status flag
    """
    pass
```

**New Functions:**

```python
async def schedule_daily_refresh():
    """
    Schedule daily instrument master refresh at 7:00 AM IST.
    
    Uses APScheduler to run refresh_master() daily.
    """
    pass
```

### 4. Database Model (database.py)

**Modified Model:**

```python
class InstrumentMaster(Base):
    """Instrument master data from broker"""
    __tablename__ = "instrument_master"
    
    # Existing fields remain the same
    
    # New composite indexes for optimization
    __table_args__ = (
        UniqueConstraint('symbol', 'exchange', name='uq_instrument'),
        Index('idx_instrument_symbol', 'symbol'),
        Index('idx_instrument_token', 'token', 'exchange'),
        Index('idx_instrument_search', 'symbol', 'name'),
        # NEW: Composite index for option chain queries
        Index('idx_option_chain_query', 'symbol', 'exchange', 'expiry', 'option_type', 'strike'),
        # NEW: Index for expiry filtering
        Index('idx_instrument_expiry', 'expiry'),
        # NEW: Index for option type filtering
        Index('idx_instrument_option_type', 'option_type'),
    )
```

### 5. API Endpoints

**New Endpoint:**

```python
@router.get("/health/instruments")
async def get_instrument_health():
    """
    Check health status of instrument master data.
    
    Returns:
        {
            "available": bool,
            "count": int,
            "last_updated": str,
            "is_stale": bool,
            "message": str
        }
    """
    pass
```

**New Admin Endpoint:**

```python
@router.post("/admin/refresh-instruments")
async def manual_refresh_instruments():
    """
    Manually trigger instrument master refresh.
    
    Requires admin authentication.
    
    Returns:
        {
            "success": bool,
            "count": int,
            "message": str
        }
    """
    pass
```

## Data Models

### Instrument Master File Format

The Angel One instrument master file is a JSON array with the following structure:

```json
[
  {
    "token": "43725",
    "symbol": "NIFTY30JAN2523000CE",
    "name": "NIFTY",
    "expiry": "30JAN2025",
    "strike": "23000.00",
    "lotsize": "25",
    "instrumenttype": "OPTIDX",
    "exch_seg": "NFO",
    "tick_size": "5.00"
  },
  {
    "token": "43726",
    "symbol": "NIFTY30JAN2523000PE",
    "name": "NIFTY",
    "expiry": "30JAN2025",
    "strike": "23000.00",
    "lotsize": "25",
    "instrumenttype": "OPTIDX",
    "exch_seg": "NFO",
    "tick_size": "5.00"
  }
]
```

### Database Schema

```sql
CREATE TABLE instrument_master (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(50) NOT NULL,
    token VARCHAR(20) NOT NULL,
    name VARCHAR(100),
    exchange VARCHAR(10) NOT NULL,
    instrument_type VARCHAR(20),
    lot_size INTEGER DEFAULT 1,
    tick_size FLOAT DEFAULT 0.05,
    expiry VARCHAR(20),
    strike FLOAT,
    option_type VARCHAR(5),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    CONSTRAINT uq_instrument UNIQUE (symbol, exchange)
);

-- Indexes for performance
CREATE INDEX idx_instrument_symbol ON instrument_master(symbol);
CREATE INDEX idx_instrument_token ON instrument_master(token, exchange);
CREATE INDEX idx_instrument_search ON instrument_master(symbol, name);
CREATE INDEX idx_option_chain_query ON instrument_master(symbol, exchange, expiry, option_type, strike);
CREATE INDEX idx_instrument_expiry ON instrument_master(expiry);
CREATE INDEX idx_instrument_option_type ON instrument_master(option_type);
```

### Option Chain Query Pattern

```python
# Query for NIFTY options expiring on 30JAN25
query = (
    select(InstrumentMaster)
    .where(
        InstrumentMaster.name == "NIFTY",
        InstrumentMaster.exchange == "NFO",
        InstrumentMaster.expiry == "30JAN25",
        InstrumentMaster.option_type.in_(["CE", "PE"])
    )
    .order_by(InstrumentMaster.strike.asc())
)
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property Reflection

After analyzing all acceptance criteria, I identified the following redundancies:
- Properties 1.2 and 2.1 both test parsing and storing - can be combined into one comprehensive property
- Properties 3.2 and 3.3 both test query correctness - 3.3 is more specific and comprehensive
- Properties 4.1 and 4.2 both test batching - 4.2 subsumes 4.1 by verifying correct API call count
- Properties 2.5 and 2.1 both verify storage - logging is a side effect of storage, not a separate property
- Properties 6.2 and 6.3 both test availability checking - health check is the formal interface for this

### Properties

Property 1: Instrument Master Parsing and Storage
*For any* valid instrument master JSON file, parsing and storing the instruments should result in all records being present in the database with correct field mappings.
**Validates: Requirements 1.2, 2.1**

Property 2: Download Retry with Exponential Backoff
*For any* download failure scenario, the system should retry up to 3 times with exponentially increasing delays (1s, 2s, 4s) before giving up.
**Validates: Requirements 1.3**

Property 3: JSON Validation
*For any* JSON input with missing or invalid required fields (symbol, token, exchange), the validation should reject the record and log the specific validation error.
**Validates: Requirements 1.5**

Property 4: Idempotent Storage
*For any* set of instrument records, storing them multiple times should result in the same database state as storing them once (no duplicates).
**Validates: Requirements 2.3**

Property 5: Atomic Transaction Updates
*For any* bulk insert operation, if an error occurs mid-insert, either all records should be stored or no records should be stored (transaction rollback).
**Validates: Requirements 2.4**

Property 6: Database Query Instead of API
*For any* option chain request, the system should query the database for instrument tokens and make zero search API calls.
**Validates: Requirements 3.1**

Property 7: Complete Option Chain Results
*For any* underlying symbol and expiry date, querying for options should return all matching CE and PE options sorted by strike price in ascending order.
**Validates: Requirements 3.2, 3.3, 3.4**

Property 8: Batch Quote API Call Count
*For any* list of N instrument tokens, the number of batch quote API calls should equal ceil(N / 50).
**Validates: Requirements 4.1, 4.2**

Property 9: Batch Result Completeness
*For any* batched quote request with N tokens, the combined response should contain exactly N quote results (assuming all tokens are valid).
**Validates: Requirements 4.4**

Property 10: Batch Retry Logic
*For any* batch quote request that fails, the system should retry that specific batch up to 2 times before propagating the error.
**Validates: Requirements 4.5**

Property 11: Refresh Process Consistency
*For any* instrument master refresh (whether at startup or scheduled), the download, parse, and store process should behave identically and produce the same database state.
**Validates: Requirements 5.3**

Property 12: Concurrent Request Safety
*For any* ongoing API requests during instrument master refresh, those requests should complete successfully without errors or data corruption.
**Validates: Requirements 5.5**

Property 13: Health Check Accuracy
*For any* database state, the health check endpoint should accurately report whether instrument data is available, the count of instruments, and whether data is stale (>48 hours old).
**Validates: Requirements 6.2, 6.3**

Property 14: Cache Consistency
*For any* instrument lookup, cached results should be identical to database query results for the same lookup parameters.
**Validates: Requirements 7.4**



## Error Handling

### Download Failures

**Scenario**: Instrument master file download fails (network error, server unavailable)

**Handling**:
1. Log error with full details (URL, status code, error message)
2. Retry up to 3 times with exponential backoff (1s, 2s, 4s)
3. If all retries fail:
   - On startup: Log critical warning and continue startup
   - On scheduled refresh: Log error and retain existing data
4. Set health status to indicate download failure

**Error Response**:
```python
{
    "error": "INSTRUMENT_MASTER_DOWNLOAD_FAILED",
    "message": "Failed to download instrument master after 3 retries",
    "details": {
        "url": "https://...",
        "last_error": "Connection timeout",
        "retry_count": 3
    }
}
```

### Parse Failures

**Scenario**: Downloaded file is not valid JSON or has unexpected structure

**Handling**:
1. Log parse error with file size and first 500 characters
2. Validate JSON structure before processing
3. Skip invalid records and log validation errors
4. Continue processing valid records
5. Return count of successful and failed records

**Error Response**:
```python
{
    "error": "INSTRUMENT_PARSE_ERROR",
    "message": "Failed to parse instrument master file",
    "details": {
        "total_records": 200000,
        "successful": 199500,
        "failed": 500,
        "sample_errors": ["Missing token field", "Invalid strike price"]
    }
}
```

### Database Failures

**Scenario**: Database connection lost or transaction fails during bulk insert

**Handling**:
1. Wrap all database operations in transactions
2. On error, rollback transaction to prevent partial updates
3. Log error with transaction details
4. Retry transaction once after 1 second delay
5. If retry fails, propagate error and maintain previous data

**Error Response**:
```python
{
    "error": "DATABASE_TRANSACTION_FAILED",
    "message": "Failed to store instruments in database",
    "details": {
        "operation": "bulk_insert",
        "records_attempted": 200000,
        "error": "Connection lost"
    }
}
```

### Option Chain Query Failures

**Scenario**: No instruments found in database for requested option chain

**Handling**:
1. Check if instrument master data exists
2. If no data: Return error indicating instrument master not loaded
3. If data exists but no matches: Return empty option chain with spot price
4. Log query parameters for debugging

**Error Response**:
```python
{
    "error": "INSTRUMENT_DATA_UNAVAILABLE",
    "message": "Instrument master data not available. Please try again later.",
    "details": {
        "health_check": "/api/health/instruments",
        "manual_refresh": "/api/admin/refresh-instruments"
    }
}
```

### Batch Quote Failures

**Scenario**: Batch quote API call fails (rate limit, network error)

**Handling**:
1. Retry failed batch up to 2 times with 500ms delay
2. If batch continues to fail, mark those instruments as unavailable
3. Continue processing other batches
4. Return partial results with error indication
5. Log failed tokens for investigation

**Error Response**:
```python
{
    "spot_price": 23500.50,
    "expiry": "30JAN25",
    "calls": [...],  # Successful results
    "puts": [...],   # Successful results
    "errors": [
        {
            "batch": 2,
            "tokens": ["43725", "43726"],
            "error": "Rate limit exceeded",
            "retry_count": 2
        }
    ]
}
```

### Stale Data Warnings

**Scenario**: Instrument master data is older than 48 hours

**Handling**:
1. Check data age on every option chain request
2. If stale (>48 hours): Log warning but continue serving requests
3. Include staleness indicator in health check response
4. Trigger automatic refresh attempt
5. Notify administrators via logs

**Warning Log**:
```
WARNING: Instrument master data is stale (last updated: 2025-01-28 07:00:00, age: 52 hours)
Attempting automatic refresh...
```

## Testing Strategy

### Dual Testing Approach

This feature requires both unit tests and property-based tests to ensure comprehensive coverage:

**Unit Tests**: Focus on specific examples, edge cases, and integration points
- Startup script initialization
- Database schema and indexes
- API endpoint responses
- Error handling scenarios
- Health check endpoint

**Property-Based Tests**: Verify universal properties across all inputs
- Parsing and storage correctness
- Query result completeness
- Batching logic
- Retry mechanisms
- Cache consistency

### Property-Based Testing Configuration

**Library**: Use `hypothesis` for Python property-based testing

**Configuration**:
- Minimum 100 iterations per property test
- Each test tagged with feature name and property number
- Tag format: `# Feature: option-chain-rate-limit-fix, Property N: [property text]`

**Example Property Test**:
```python
from hypothesis import given, strategies as st
import pytest

# Feature: option-chain-rate-limit-fix, Property 8: Batch Quote API Call Count
@given(
    token_count=st.integers(min_value=1, max_value=500)
)
@pytest.mark.property_test
async def test_batch_api_call_count(token_count):
    """
    For any list of N instrument tokens, 
    the number of batch quote API calls should equal ceil(N / 50).
    """
    # Generate N random tokens
    tokens = [f"token_{i}" for i in range(token_count)]
    
    # Mock API call counter
    api_call_count = 0
    
    # Execute batching logic
    batches = create_batches(tokens, batch_size=50)
    
    # Verify API call count
    expected_calls = math.ceil(token_count / 50)
    assert len(batches) == expected_calls
```

### Unit Test Coverage

**Symbol Service Tests** (`test_services/test_symbol.py`):
- `test_download_instrument_master_success`: Verify successful download
- `test_download_instrument_master_retry`: Verify retry logic on failure
- `test_parse_instrument_record_valid`: Verify parsing valid records
- `test_parse_instrument_record_invalid`: Verify handling invalid records
- `test_store_instruments_bulk`: Verify bulk insert
- `test_query_options_by_expiry`: Verify option chain queries
- `test_get_instrument_health`: Verify health check logic

**Angel One Adapter Tests** (`test_brokers/test_angelone.py`):
- `test_get_option_chain_database_query`: Verify database is queried instead of API
- `test_get_option_chain_batch_quotes`: Verify batch quote requests
- `test_get_quotes_batch_optimized`: Verify batching logic
- `test_option_chain_no_api_search_calls`: Verify no search API calls

**Startup Script Tests** (`test_scripts/test_startup.py`):
- `test_init_instrument_master_success`: Verify successful initialization
- `test_init_instrument_master_failure_continues`: Verify startup continues on failure
- `test_schedule_daily_refresh`: Verify scheduler configuration

**API Endpoint Tests** (`test_api/test_endpoints.py`):
- `test_health_instruments_endpoint`: Verify health check endpoint
- `test_manual_refresh_endpoint`: Verify manual refresh endpoint
- `test_option_chain_with_instruments`: Verify option chain with database data
- `test_option_chain_without_instruments`: Verify error when data unavailable

### Integration Tests

**End-to-End Option Chain Flow**:
1. Start application with empty database
2. Trigger instrument master download
3. Verify data is stored in database
4. Request option chain for NIFTY
5. Verify response contains options
6. Verify only 2-3 API calls were made (batch quotes only)
7. Verify no search API calls were made

**Refresh Flow**:
1. Load initial instrument master
2. Trigger manual refresh
3. Verify data is updated
4. Verify ongoing requests are not interrupted
5. Verify health check reflects new data

**Failure Recovery Flow**:
1. Simulate download failure on startup
2. Verify application starts successfully
3. Verify health check indicates unavailable data
4. Trigger manual refresh
5. Verify data becomes available
6. Verify option chain requests now work

### Performance Testing

While not part of correctness properties, performance should be validated:

**Database Query Performance**:
- Measure query time for option chain queries
- Target: <50ms for typical queries
- Use EXPLAIN ANALYZE to verify index usage

**Option Chain Response Time**:
- Measure end-to-end response time
- Target: <2 seconds for chains with 100 strikes
- Compare before/after implementation

**API Call Reduction**:
- Count API calls before fix: 100+ per option chain
- Count API calls after fix: 2-3 per option chain
- Verify 97% reduction in API calls

### Test Data Generation

**Instrument Master Test Data**:
```python
def generate_test_instruments(count: int = 1000) -> List[Dict]:
    """Generate realistic test instrument data"""
    instruments = []
    underlyings = ["NIFTY", "BANKNIFTY", "FINNIFTY"]
    expiries = ["30JAN25", "06FEB25", "13FEB25"]
    strikes = range(20000, 25000, 50)
    
    for underlying in underlyings:
        for expiry in expiries:
            for strike in strikes:
                for option_type in ["CE", "PE"]:
                    instruments.append({
                        "token": f"{random.randint(10000, 99999)}",
                        "symbol": f"{underlying}{expiry}{strike}{option_type}",
                        "name": underlying,
                        "expiry": expiry,
                        "strike": str(strike),
                        "lotsize": "25",
                        "instrumenttype": "OPTIDX",
                        "exch_seg": "NFO",
                        "tick_size": "5.00"
                    })
    
    return instruments[:count]
```

### Continuous Testing

**Pre-commit Hooks**:
- Run unit tests on changed files
- Run property tests with reduced iterations (10)

**CI/CD Pipeline**:
- Run full unit test suite
- Run property tests with full iterations (100)
- Run integration tests
- Measure and report API call reduction
- Verify database query performance

**Monitoring in Production**:
- Track instrument master refresh success rate
- Monitor option chain response times
- Alert on stale data (>48 hours)
- Track API call counts to verify reduction
