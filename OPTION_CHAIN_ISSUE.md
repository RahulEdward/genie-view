# Option Chain Issue - Rate Limit Exceeded

## Problem
The option chain is not loading because the backend is hitting Angel One API rate limits (403 errors).

## Root Cause
Angel One doesn't provide a direct option chain API. The current implementation:
1. Searches for each option symbol individually using the search API
2. Makes hundreds of API calls for a single option chain request
3. Quickly exceeds Angel One's rate limit (typically 25-30 requests per minute)

## Evidence from Logs
```
2026-01-25 12:04:13 | ERROR | HTTP error: 403 - Access denied because of exceeding access rate
2026-01-25 12:04:14 | WARNING | Search API error for 'NIFTY27JAN2627650CE' on NFO: Access denied
```

## Solution Required
Use the **Instrument Master File** approach instead of search API:

### Current Flow (BROKEN):
```
User requests option chain
  → Backend searches for "NIFTY27JAN2625000CE" (API call)
  → Backend searches for "NIFTY27JAN2625000PE" (API call)
  → Backend searches for "NIFTY27JAN2625050CE" (API call)
  → ... (100+ API calls)
  → Rate limit exceeded → No data
```

### Correct Flow (NEEDED):
```
User requests option chain
  → Backend loads instrument master from database/cache
  → Filter options from master file (no API calls)
  → Get quotes for filtered options in batches (2-3 API calls)
  → Return option chain data
```

## Implementation Steps

### 1. Download Instrument Master
Angel One provides instrument master files:
- URL: `https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json`
- Contains all tradable instruments with tokens
- Updated daily

### 2. Store in Database
- Download master file on startup
- Store in `instruments` table
- Index by: symbol, exchange, expiry, strike, option_type

### 3. Modify Option Chain Logic
Instead of searching:
```python
# OLD (causes rate limits)
for strike in strikes:
    symbol = f"{underlying}{expiry}{strike}CE"
    result = await self.search_symbols(symbol, exchange)  # API call!
    
# NEW (uses master file)
instruments = await db.query(Instrument).filter(
    Instrument.underlying == underlying,
    Instrument.exchange == exchange,
    Instrument.expiry == expiry,
    Instrument.option_type.in_(['CE', 'PE'])
).all()  # No API call!
```

### 4. Batch Quote Requests
```python
# Get quotes for all options in batches of 50
batch_size = 50
for i in range(0, len(instruments), batch_size):
    batch = instruments[i:i+batch_size]
    quotes = await self.get_quotes_batch(batch)  # 1 API call per 50 symbols
```

## Temporary Workaround
Until the proper fix is implemented:
1. **Increase delays** between API calls (currently 0.2s, increase to 2s)
2. **Reduce strike count** (request only 5 strikes instead of 10-15)
3. **Add caching** with longer TTL (5 minutes instead of 30 seconds)
4. **Wait for rate limit reset** (Angel One resets every minute)

## Files to Modify
1. `backend/app/brokers/angelone/adapter.py` - get_option_chain method
2. `backend/app/services/symbol.py` - Add instrument master download
3. `backend/app/models/database.py` - Add Instrument model if not exists
4. `backend/scripts/startup.py` - Download master on startup

## Priority
**HIGH** - Option chain is a core feature and currently non-functional due to rate limits.

## Estimated Effort
- Proper fix with instrument master: 4-6 hours
- Temporary workaround: 30 minutes

## References
- Angel One API Docs: https://smartapi.angelbroking.com/docs
- Instrument Master: https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json
- Rate Limits: 25 requests per minute per API key
