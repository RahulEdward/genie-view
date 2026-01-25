"""
Database Models
SQLAlchemy ORM models for PostgreSQL
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, 
    Index, UniqueConstraint, Text, Boolean
)
from app.db.session import Base


class OHLCHistory(Base):
    """Historical OHLC candle data"""
    __tablename__ = "ohlc_history"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(50), nullable=False)
    exchange = Column(String(10), nullable=False)
    interval = Column(String(20), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint('symbol', 'exchange', 'interval', 'timestamp', name='uq_ohlc_candle'),
        Index('idx_ohlc_symbol_exchange_interval', 'symbol', 'exchange', 'interval'),
        Index('idx_ohlc_timestamp', 'timestamp'),
    )


class UserSession(Base):
    """User authentication sessions"""
    __tablename__ = "user_sessions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    api_key = Column(String(100), unique=True, nullable=False)
    broker = Column(String(20), nullable=False)
    broker_api_key = Column(Text)  # Broker's API key (encrypted)
    client_id = Column(String(50), nullable=False)
    jwt_token = Column(Text)
    refresh_token = Column(Text)
    feed_token = Column(String(200))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    expires_at = Column(DateTime)
    
    __table_args__ = (
        Index('idx_session_api_key', 'api_key'),
        Index('idx_session_client_id', 'client_id'),
    )


class InstrumentMaster(Base):
    """Instrument master data from broker"""
    __tablename__ = "instrument_master"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(50), nullable=False)
    token = Column(String(20), nullable=False)
    name = Column(String(100))
    exchange = Column(String(10), nullable=False)
    instrument_type = Column(String(20))
    lot_size = Column(Integer, default=1)
    tick_size = Column(Float, default=0.05)
    expiry = Column(String(20))
    strike = Column(Float)
    option_type = Column(String(5))
    updated_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint('symbol', 'exchange', name='uq_instrument'),
        Index('idx_instrument_symbol', 'symbol'),
        Index('idx_instrument_token', 'token', 'exchange'),
        Index('idx_instrument_search', 'symbol', 'name'),
        # Composite index for option chain queries (optimized for filtering by multiple fields)
        Index('idx_option_chain_query', 'name', 'exchange', 'expiry', 'option_type', 'strike'),
        # Index for expiry filtering
        Index('idx_instrument_expiry', 'expiry'),
        # Index for option type filtering
        Index('idx_instrument_option_type', 'option_type'),
    )


class CachedOptionChain(Base):
    """Cached option chain data with TTL"""
    __tablename__ = "cached_option_chain"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    underlying = Column(String(50), nullable=False)
    exchange = Column(String(10), nullable=False)
    expiry = Column(String(20))
    data = Column(Text)  # JSON serialized option chain
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    
    __table_args__ = (
        Index('idx_option_chain_underlying', 'underlying', 'exchange', 'expiry'),
    )


class MarketHoliday(Base):
    """Market holidays data"""
    __tablename__ = "market_holidays"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String(10), nullable=False)  # YYYY-MM-DD
    description = Column(String(100))
    holiday_type = Column(String(30))
    exchanges = Column(Text)  # JSON array of closed exchanges
    year = Column(Integer, nullable=False)
    
    __table_args__ = (
        UniqueConstraint('date', name='uq_holiday_date'),
        Index('idx_holiday_year', 'year'),
    )


class BrokerCredentials(Base):
    """Stored broker credentials (encrypted)"""
    __tablename__ = "broker_credentials"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    broker = Column(String(20), nullable=False)
    client_id = Column(String(50), nullable=False)
    api_key = Column(Text, nullable=False)  # Encrypted
    password = Column(Text)  # Encrypted (optional - for auto-login)
    totp_secret = Column(Text)  # Encrypted (optional - for auto-TOTP)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint('broker', 'client_id', name='uq_broker_client'),
        Index('idx_broker_credentials_client', 'client_id'),
    )
