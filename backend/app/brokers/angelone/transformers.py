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
    
    Angel One returns nested structure with fetched array
    """
    fetched = data.get("fetched", [])
    
    if not fetched:
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
    
    item = fetched[0]
    
    return Quote(
        symbol=symbol,
        exchange=exchange,
        ltp=float(item.get("ltp", 0)),
        open=float(item.get("open", 0)),
        high=float(item.get("high", 0)),
        low=float(item.get("low", 0)),
        prev_close=float(item.get("close", item.get("prevClose", 0))),
        volume=int(item.get("tradeVolume", item.get("volume", 0))),
        timestamp=int(datetime.now().timestamp()),
        bid=float(item.get("depth", {}).get("buy", [{}])[0].get("price", 0)) if item.get("depth") else None,
        ask=float(item.get("depth", {}).get("sell", [{}])[0].get("price", 0)) if item.get("depth") else None,
        bid_qty=int(item.get("depth", {}).get("buy", [{}])[0].get("quantity", 0)) if item.get("depth") else None,
        ask_qty=int(item.get("depth", {}).get("sell", [{}])[0].get("quantity", 0)) if item.get("depth") else None
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
    elif instrument_type in ["OPTIDX", "OPTSTK"]:
        # Try to parse from symbol
        if symbol.endswith("CE"):
            option_type = "CE"
        elif symbol.endswith("PE"):
            option_type = "PE"
    
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


def normalize_expiry(expiry: str) -> str:
    """
    Normalize expiry date to DDMMMYY format.
    
    Handles formats like:
    - "2025-01-30" -> "30JAN25"
    - "30-JAN-2025" -> "30JAN25"
    - "30JAN25" -> "30JAN25"
    """
    if not expiry:
        return ""
    
    # Already in correct format
    if len(expiry) == 7 and expiry[2:5].isalpha():
        return expiry.upper()
    
    # Try ISO format
    try:
        if "-" in expiry and len(expiry) == 10:
            dt = datetime.strptime(expiry, "%Y-%m-%d")
            return dt.strftime("%d%b%y").upper()
    except ValueError:
        pass
    
    # Try DD-MMM-YYYY format
    try:
        if "-" in expiry:
            dt = datetime.strptime(expiry, "%d-%b-%Y")
            return dt.strftime("%d%b%y").upper()
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
