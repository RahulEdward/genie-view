"""
Angel One Data Transformers
Transform broker-specific responses to standardized format
"""

from datetime import datetime
from typing import Dict, List, Tuple, Any, Optional

from app.brokers.base import OHLCCandle, Quote, SymbolInfo
from app.brokers.angelone.endpoints import ERROR_CODE_MAP


def transform_candle_data(data: List) -> List[OHLCCandle]:
    """
    Transform Angel One candle data to OHLCCandle list.
    
    Angel One returns: [[timestamp, open, high, low, close, volume], ...]
    """
    candles = []
    
    for row in data:
        if len(row) >= 6:
            # Parse timestamp - Angel One returns ISO format string
            timestamp = row[0]
            if isinstance(timestamp, str):
                try:
                    dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                    timestamp = int(dt.timestamp())
                except ValueError:
                    continue
            
            candles.append(OHLCCandle(
                timestamp=timestamp,
                open=float(row[1]),
                high=float(row[2]),
                low=float(row[3]),
                close=float(row[4]),
                volume=int(row[5])
            ))
    
    return candles


def transform_quote_data(
    data: Dict,
    symbol: str,
    exchange: str
) -> Quote:
    """
    Transform Angel One quote data to Quote.
    
    start:
    Handles both full response ({fetched: [...]}) and single item ({ltp: ...})
    """
    # Check if data Is the item (batch processing passes items directly)
    if "ltp" in data or "symbolToken" in data:
        item = data
    else:
        # Try to extract from fetched list (single quote API response)
        fetched = data.get("fetched", [])
        if fetched:
            item = fetched[0]
        else:
            # Return empty quote
            return Quote(
                symbol=symbol,
                exchange=exchange,
                ltp=0,
                open=0,
                high=0,
                low=0,
                prev_close=0,
                volume=0,
                timestamp=int(datetime.now().timestamp())
            )
    
    # Parse fields safely
    try:
        ltp = float(item.get("ltp", 0))
    except (ValueError, TypeError):
        ltp = 0.0
        
    try:
        open_px = float(item.get("open", 0))
        high_px = float(item.get("high", 0))
        low_px = float(item.get("low", 0))
        prev_close = float(item.get("close", item.get("prevClose", 0)))
        volume = int(item.get("tradeVolume", item.get("volume", 0)))
        oi = int(item.get("opninterest", item.get("oi", 0)))  # Open Interest
    except (ValueError, TypeError):
        open_px = 0.0
        high_px = 0.0
        low_px = 0.0
        prev_close = 0.0
        volume = 0
        oi = 0
    
    return Quote(
        symbol=symbol,
        exchange=exchange,
        ltp=ltp,
        open=open_px,
        high=high_px,
        low=low_px,
        prev_close=prev_close,
        volume=volume,
        oi=oi,
        timestamp=int(datetime.now().timestamp()),
        bid=float(item.get("depth", {}).get("buy", [{}])[0].get("price", 0)) if item.get("depth") and item.get("depth", {}).get("buy") else None,
        ask=float(item.get("depth", {}).get("sell", [{}])[0].get("price", 0)) if item.get("depth") and item.get("depth", {}).get("sell") else None,
        bid_qty=int(item.get("depth", {}).get("buy", [{}])[0].get("quantity", 0)) if item.get("depth") and item.get("depth", {}).get("buy") else None,
        ask_qty=int(item.get("depth", {}).get("sell", [{}])[0].get("quantity", 0)) if item.get("depth") and item.get("depth", {}).get("sell") else None
    )


def transform_symbol_info(data: Dict) -> SymbolInfo:
    """
    Transform Angel One symbol data to SymbolInfo.
    
    Handles both search results and instrument master format
    """
    # Handle different field names
    symbol = data.get("tradingsymbol", data.get("symbol", ""))
    token = data.get("symboltoken", data.get("token", ""))
    name = data.get("name", data.get("companyname", ""))
    exchange = data.get("exchange", data.get("exch_seg", ""))
    
    # Parse instrument type
    instrument_type = data.get("instrumenttype", data.get("instrument_type", ""))
    
    # Parse lot size
    lot_size = int(data.get("lotsize", data.get("lot_size", 1)) or 1)
    
    # Parse tick size
    tick_size = float(data.get("tick_size", data.get("ticksize", 0.05)) or 0.05)
    
    # Parse expiry
    expiry = data.get("expiry", "")
    if expiry:
        # Convert from various formats to DDMMMYY
        expiry = normalize_expiry(expiry)
    
    # Parse strike and option type
    strike = None
    option_type = None
    
    if data.get("strike"):
        strike = float(data["strike"])
    
    if data.get("optiontype"):
        option_type = data["optiontype"]
    
    # Always check symbol for CE/PE if not set or even if set (verification)
    if symbol.endswith("CE"):
        option_type = "CE"
        if not instrument_type:
            instrument_type = "OPTIDX" if any(idx in symbol for idx in ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"]) else "OPTSTK"
    elif symbol.endswith("PE"):
        option_type = "PE"
        if not instrument_type:
            instrument_type = "OPTIDX" if any(idx in symbol for idx in ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"]) else "OPTSTK"
        
    # If it's an option, try to extract strike and expiry if missing
    if option_type:
        if not strike:
            strike = _extract_strike_from_symbol(symbol)
        
        if not expiry:
            # Try to extract expiry from symbol (7-char format)
            import re
            match = re.search(r'(\d{2}[A-Z]{3}\d{2})', symbol, re.IGNORECASE)
            if match:
                expiry = normalize_expiry(match.group(1))
    
    return SymbolInfo(
        symbol=symbol,
        token=token,
        name=name,
        exchange=exchange,
        instrument_type=instrument_type,
        lot_size=lot_size,
        tick_size=tick_size,
        expiry=expiry,
        strike=strike,
        option_type=option_type
    )


def _extract_strike_from_symbol(symbol: str) -> Optional[float]:
    """
    Extract strike price from option symbol.
    
    Examples:
    - RELIANCE30JAN2526000CE -> 26000
    - NIFTY30JAN2524000CE -> 24000
    - BANKNIFTY30JAN2550000PE -> 50000
    """
    import re
    
    # Remove CE/PE suffix
    symbol_base = symbol[:-2] if symbol.endswith(('CE', 'PE')) else symbol
    
    # Pattern: ends with digits after expiry date (DDMMMYY or DDMMMYYYY)
    # Extract the numeric part after the date
    # Support both 2-digit and 4-digit years
    match = re.search(r'\d{2}[A-Z]{3}(?:\d{4}|\d{2})(\d+)$', symbol_base)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            pass
    
    return None


def normalize_expiry(expiry: str) -> str:
    """
    Normalize expiry date to DDMMMYYYY format (4-digit year).
    
    Handles formats like:
    - "2025-01-30" -> "30JAN2025"
    - "30-JAN-2025" -> "30JAN2025"
    - "30JAN25" -> "30JAN2025"
    - "30JAN2025" -> "30JAN2025"
    
    Returns 4-digit year format to match instrument master database.
    """
    if not expiry:
        return ""
    
    # Already in DDMMMYYYY format (9 chars)
    if len(expiry) == 9 and expiry[2:5].isalpha():
        return expiry.upper()
    
    # DDMMMYY format (7 chars) -> convert to DDMMMYYYY
    if len(expiry) == 7 and expiry[2:5].isalpha():
        # Extract 2-digit year and convert to 4-digit
        yy = expiry[5:7]
        # Assume 20xx for years 00-99
        yyyy = "20" + yy
        return (expiry[:5] + yyyy).upper()

    # Try ISO format (YYYY-MM-DD)
    try:
        if "-" in expiry and len(expiry) == 10:
            dt = datetime.strptime(expiry, "%Y-%m-%d")
            return dt.strftime("%d%b%Y").upper()
    except ValueError:
        pass
    
    # Try DD-MMM-YYYY format
    try:
        if "-" in expiry:
            # Handle both 2-digit and 4-digit years
            fmt = "%d-%b-%Y" if len(expiry.split("-")[-1]) == 4 else "%d-%b-%y"
            dt = datetime.strptime(expiry, fmt)
            return dt.strftime("%d%b%Y").upper()
    except ValueError:
        pass
    
    return expiry.upper()


def parse_angel_error(response: Dict) -> Tuple[str, str]:
    """
    Parse Angel One error response.
    
    Returns: (error_code, error_message)
    """
    error_code = response.get("errorcode", response.get("errorCode", ""))
    message = response.get("message", response.get("errorMessage", "Unknown error"))
    
    # Map to internal error code
    if error_code in ERROR_CODE_MAP:
        internal_code, default_msg = ERROR_CODE_MAP[error_code]
        return internal_code, message or default_msg
    
    return "BROKER_ERROR", message


def transform_option_data(data: Dict) -> Dict:
    """Transform option data for option chain"""
    return {
        "symbol": data.get("tradingsymbol", ""),
        "token": data.get("symboltoken", ""),
        "ltp": float(data.get("ltp", 0)),
        "prev_close": float(data.get("close", 0)),
        "open": float(data.get("open", 0)),
        "high": float(data.get("high", 0)),
        "low": float(data.get("low", 0)),
        "bid": float(data.get("bidprice", 0)),
        "ask": float(data.get("askprice", 0)),
        "oi": int(data.get("opninterest", 0)),
        "volume": int(data.get("volume", 0)),
        "lot_size": int(data.get("lotsize", 1))
    }
