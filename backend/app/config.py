"""
Application Configuration
Uses pydantic-settings for environment variable management
"""

from functools import lru_cache
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

# Get the backend directory (where .env file is located)
BACKEND_DIR = Path(__file__).resolve().parent.parent
DEFAULT_SQLITE_URL = f"sqlite+aiosqlite:///{BACKEND_DIR}/trading.db"


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # App Settings
    app_name: str = "Trading Backend"
    app_version: str = "1.0.0"
    debug: bool = False
    
    # Server Settings
    host: str = "0.0.0.0"
    port: int = 8000
    ws_port: int = 8765
    
    # Database Settings - use property to handle empty string
    database_url: Optional[str] = None
    
    @property
    def db_url(self) -> str:
        """Get database URL, defaulting to SQLite if not set"""
        if self.database_url and self.database_url.strip():
            return self.database_url
        return DEFAULT_SQLITE_URL
    
    # Redis Settings (optional - will work without Redis)
    redis_url: str = "redis://localhost:6379/0"
    cache_ttl: int = 300  # 5 minutes default
    
    # Security
    SECRET_KEY: str = "your-secret-key-change-in-production-32chars"
    
    # Broker Settings
    default_broker: str = "angelone"
    
    # Angel One Settings
    angelone_api_key: Optional[str] = None
    angelone_client_id: Optional[str] = None
    angelone_password: Optional[str] = None
    angelone_totp_secret: Optional[str] = None
    
    # Rate Limiting
    rate_limit_requests: int = 30
    rate_limit_window: int = 60  # seconds
    
    # JWT Settings
    jwt_secret_key: str = "your-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60
    
    # Logging
    log_level: str = "INFO"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


settings = get_settings()
