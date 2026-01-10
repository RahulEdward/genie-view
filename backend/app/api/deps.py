"""
API Dependencies
Dependency injection for FastAPI endpoints
"""

from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.models.database import UserSession
from app.models.schemas import ErrorCodes, ERROR_MESSAGES

# API Key header
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def get_api_key(
    api_key: Optional[str] = Depends(api_key_header),
) -> str:
    """Extract API key from header or raise error"""
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "status": "error",
                "code": ErrorCodes.AUTH_FAILED,
                "message": "API key required"
            }
        )
    return api_key


async def validate_api_key(
    api_key: str = Depends(get_api_key),
    db: AsyncSession = Depends(get_db)
) -> UserSession:
    """Validate API key and return session"""
    result = await db.execute(
        select(UserSession).where(
            UserSession.api_key == api_key,
            UserSession.is_active == True
        )
    )
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "status": "error",
                "code": ErrorCodes.INVALID_TOKEN,
                "message": ERROR_MESSAGES[ErrorCodes.INVALID_TOKEN]
            }
        )
    
    return session


async def get_optional_api_key(
    api_key: Optional[str] = Depends(api_key_header),
) -> Optional[str]:
    """Get optional API key (for endpoints that work with or without auth)"""
    return api_key


class RateLimiter:
    """Rate limiter dependency"""
    
    def __init__(self, requests: int = 30, window: int = 60):
        self.requests = requests
        self.window = window
    
    async def __call__(self, api_key: Optional[str] = Depends(get_optional_api_key)):
        """Rate limit by API key if provided, otherwise skip rate limiting"""
        if not api_key:
            # No API key in header - the endpoint will validate from request body
            # Skip rate limiting here, let endpoint handle auth
            return None
        
        from app.utils.cache import get_redis
        
        redis = get_redis()
        key = f"rate_limit:{api_key}"
        
        current = await redis.get(key)
        if current is None:
            await redis.setex(key, self.window, 1)
        elif int(current) >= self.requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "status": "error",
                    "code": ErrorCodes.RATE_LIMITED,
                    "message": ERROR_MESSAGES[ErrorCodes.RATE_LIMITED]
                }
            )
        else:
            await redis.incr(key)
        
        return api_key


# Pre-configured rate limiters
default_rate_limiter = RateLimiter(requests=30, window=60)
strict_rate_limiter = RateLimiter(requests=10, window=60)
