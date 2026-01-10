"""
Angel One SmartAPI Endpoints and Constants
"""

# Base URLs
BASE_URL = "https://apiconnect.angelone.in"
WEBSOCKET_URL = "wss://smartapisocket.angelone.in/smart-stream"

# API Endpoints
ENDPOINTS = {
    # Authentication
    "login": "/rest/auth/angelbroking/user/v1/loginByPassword",
    "logout": "/rest/secure/angelbroking/user/v1/logout",
    "refresh_token": "/rest/auth/angelbroking/jwt/v1/generateTokens",
    "profile": "/rest/secure/angelbroking/user/v1/getProfile",
    
    # Market Data
    "candle": "/rest/secure/angelbroking/historical/v1/getCandleData",
    "quote": "/rest/secure/angelbroking/market/v1/quote",
    "ltp": "/rest/secure/angelbroking/order/v1/getLtpData",
    "market_data": "/rest/secure/angelbroking/market/v1/quote",
    
    # Search
    "search": "/rest/secure/angelbroking/order/v1/searchScrip",
    
    # Instrument Master (external URL)
    "instrument_master": "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json",
}

# Interval Mapping (internal -> Angel One format)
INTERVAL_MAP = {
    "1m": "ONE_MINUTE",
    "3m": "THREE_MINUTE",
    "5m": "FIVE_MINUTE",
    "10m": "TEN_MINUTE",
    "15m": "FIFTEEN_MINUTE",
    "30m": "THIRTY_MINUTE",
    "1h": "ONE_HOUR",
    "2h": "TWO_HOUR",
    "4h": "FOUR_HOUR",
    "1d": "ONE_DAY",
    "1w": "ONE_WEEK",
    "1M": "ONE_MONTH",
    # Also support direct Angel One format
    "ONE_MINUTE": "ONE_MINUTE",
    "THREE_MINUTE": "THREE_MINUTE",
    "FIVE_MINUTE": "FIVE_MINUTE",
    "TEN_MINUTE": "TEN_MINUTE",
    "FIFTEEN_MINUTE": "FIFTEEN_MINUTE",
    "THIRTY_MINUTE": "THIRTY_MINUTE",
    "ONE_HOUR": "ONE_HOUR",
    "ONE_DAY": "ONE_DAY",
    "ONE_WEEK": "ONE_WEEK",
    "ONE_MONTH": "ONE_MONTH",
}

# Exchange Mapping
EXCHANGE_MAP = {
    "NSE": "NSE",
    "BSE": "BSE",
    "NFO": "NFO",
    "BFO": "BFO",
    "MCX": "MCX",
    "CDS": "CDS",
    "NCDEX": "NCDEX",
    "NSE_INDEX": "NSE",
    "BSE_INDEX": "BSE",
}

# Supported Exchanges
SUPPORTED_EXCHANGES = ["NSE", "BSE", "NFO", "BFO", "MCX", "CDS", "NCDEX"]

# Exchange Type for WebSocket
EXCHANGE_TYPE_MAP = {
    "NSE": 1,
    "NFO": 2,
    "BSE": 3,
    "BFO": 4,
    "MCX": 5,
    "CDS": 13,
}

# Error Code Mapping (Angel One -> Internal)
ERROR_CODE_MAP = {
    "AB1000": ("AUTH_FAILED", "Invalid credentials"),
    "AB1001": ("INVALID_TOKEN", "Session expired or invalid token"),
    "AB1002": ("RATE_LIMITED", "Too many requests"),
    "AB1003": ("AUTH_FAILED", "Invalid TOTP"),
    "AB1004": ("BROKER_ERROR", "Something went wrong, please try again"),
    "AB1005": ("AUTH_FAILED", "Account locked"),
    "AB1006": ("AUTH_FAILED", "Invalid API key"),
    "AB1010": ("INVALID_TOKEN", "Token expired"),
    "AB2000": ("SYMBOL_NOT_FOUND", "Invalid symbol token"),
    "AB2001": ("INVALID_EXCHANGE", "Invalid exchange"),
    "AB2002": ("NO_DATA", "No data available"),
    "AG8001": ("BROKER_ERROR", "Session expired"),
}

# Default Headers
DEFAULT_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "X-UserType": "USER",
    "X-SourceID": "WEB",
    "X-ClientLocalIP": "127.0.0.1",
    "X-ClientPublicIP": "127.0.0.1",
    "X-MACAddress": "00:00:00:00:00:00",
}

# Index Symbols (for option chain underlying lookup)
INDEX_SYMBOLS = {
    "NIFTY": {"token": "99926000", "exchange": "NSE"},
    "BANKNIFTY": {"token": "99926009", "exchange": "NSE"},
    "FINNIFTY": {"token": "99926037", "exchange": "NSE"},
    "MIDCPNIFTY": {"token": "99926074", "exchange": "NSE"},
    "SENSEX": {"token": "99919000", "exchange": "BSE"},
    "BANKEX": {"token": "99919015", "exchange": "BSE"},
}

# Common NSE Equity Symbol Tokens (fallback for when search API fails)
# These are the most commonly traded NSE stocks
NSE_EQUITY_TOKENS = {
    "RELIANCE": "2885",
    "TCS": "11536",
    "HDFCBANK": "1333",
    "INFY": "1594",
    "ICICIBANK": "4963",
    "HINDUNILVR": "1394",
    "SBIN": "3045",
    "BHARTIARTL": "10604",
    "ITC": "1660",
    "KOTAKBANK": "1922",
    "LT": "11483",
    "AXISBANK": "5900",
    "ASIANPAINT": "236",
    "MARUTI": "10999",
    "HCLTECH": "7229",
    "SUNPHARMA": "3351",
    "TITAN": "3506",
    "BAJFINANCE": "317",
    "WIPRO": "3787",
    "ULTRACEMCO": "11532",
    "ONGC": "2475",
    "NTPC": "11630",
    "POWERGRID": "14977",
    "M&M": "2031",
    "TATAMOTORS": "3456",
    "TATASTEEL": "3499",
    "JSWSTEEL": "11723",
    "ADANIENT": "25",
    "ADANIPORTS": "15083",
    "COALINDIA": "20374",
    "BPCL": "526",
    "GRASIM": "1232",
    "TECHM": "13538",
    "INDUSINDBK": "5258",
    "DRREDDY": "881",
    "CIPLA": "694",
    "EICHERMOT": "910",
    "DIVISLAB": "10940",
    "APOLLOHOSP": "157",
    "BRITANNIA": "547",
    "NESTLEIND": "17963",
    "BAJAJFINSV": "16675",
    "HEROMOTOCO": "1348",
    "TATACONSUM": "3432",
    "HINDALCO": "1363",
    "SBILIFE": "21808",
    "HDFCLIFE": "467",
    "UPL": "11287",
    "SHREECEM": "3103",
}
