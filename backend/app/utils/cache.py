"""
Redis Cache Utilities
Async Redis client for caching (optional - works without Redis)
"""

import json
from typing import Any, Optional

from app.config import settings
from app.utils.logger import logger

# Global Redis client
_redis_client = None
_redis_available = False

# In-memory fallback cache
_memory_cache: dict = {}


async def init_redis():
    """Initialize Redis connection (optional - falls back to memory cache)"""
    global _redis_client, _redis_available
    
    try:
        import redis.asyncio as redis
        _redis_client = redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True
        )
        # Test connection
        await _redis_client.ping()
        _redis_available = True
        logger.info("Redis connected successfully")
    except Exception as e:
        logger.warning(f"Redis not available, using in-memory cache: {e}")
        _redis_available = False
        _redis_client = None


async def close_redis():
    """Close Redis connection"""
    global _redis_client, _redis_available
    if _redis_client and _redis_available:
        await _redis_client.close()
    _redis_client = None
    _redis_available = False


def get_redis():
    """Get Redis client instance (may be None if not available)"""
    return _redis_client if _redis_available else None


async def cache_get(key: str) -> Optional[Any]:
    """Get value from cache"""
    if _redis_available and _redis_client:
        value = await _redis_client.get(key)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return None
    else:
        # Memory cache fallback
        return _memory_cache.get(key)


async def cache_set(key: str, value: Any, ttl: Optional[int] = None) -> bool:
    """Set value in cache with optional TTL"""
    if _redis_available and _redis_client:
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
        if ttl:
            return await _redis_client.setex(key, ttl, value)
        return await _redis_client.set(key, value)
    else:
        # Memory cache fallback (ignores TTL)
        _memory_cache[key] = value
        return True


async def cache_delete(key: str) -> bool:
    """Delete key from cache"""
    if _redis_available and _redis_client:
        return await _redis_client.delete(key) > 0
    else:
        if key in _memory_cache:
            del _memory_cache[key]
            return True
        return False


async def cache_exists(key: str) -> bool:
    """Check if key exists in cache"""
    if _redis_available and _redis_client:
        return await _redis_client.exists(key) > 0
    else:
        return key in _memory_cache


async def cache_get_ttl(key: str) -> int:
    """Get remaining TTL for a key"""
    if _redis_available and _redis_client:
        return await _redis_client.ttl(key)
    return -1  # Memory cache doesn't support TTL


async def cache_set_hash(key: str, mapping: dict, ttl: Optional[int] = None) -> bool:
    """Set hash in cache"""
    if _redis_available and _redis_client:
        await _redis_client.hset(key, mapping=mapping)
        if ttl:
            await _redis_client.expire(key, ttl)
        return True
    else:
        _memory_cache[key] = mapping
        return True


async def cache_get_hash(key: str) -> Optional[dict]:
    """Get hash from cache"""
    if _redis_available and _redis_client:
        return await _redis_client.hgetall(key) or None
    else:
        return _memory_cache.get(key)


async def cache_increment(key: str, amount: int = 1) -> int:
    """Increment counter in cache"""
    if _redis_available and _redis_client:
        return await _redis_client.incrby(key, amount)
    else:
        current = _memory_cache.get(key, 0)
        _memory_cache[key] = current + amount
        return _memory_cache[key]


async def cache_keys(pattern: str) -> list:
    """Get keys matching pattern"""
    if _redis_available and _redis_client:
        return await _redis_client.keys(pattern)
    else:
        # Simple pattern matching for memory cache
        import fnmatch
        return [k for k in _memory_cache.keys() if fnmatch.fnmatch(k, pattern)]


class CacheManager:
    """Cache manager with namespace support"""
    
    def __init__(self, namespace: str = ""):
        self.namespace = namespace
    
    def _key(self, key: str) -> str:
        """Generate namespaced key"""
        if self.namespace:
            return f"{self.namespace}:{key}"
        return key
    
    async def get(self, key: str) -> Optional[Any]:
        return await cache_get(self._key(key))
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        return await cache_set(self._key(key), value, ttl or settings.cache_ttl)
    
    async def delete(self, key: str) -> bool:
        return await cache_delete(self._key(key))
    
    async def exists(self, key: str) -> bool:
        return await cache_exists(self._key(key))


# Pre-configured cache managers
history_cache = CacheManager("history")
quote_cache = CacheManager("quote")
option_cache = CacheManager("option")
option_chain_cache = CacheManager("optionchain")
symbol_cache = CacheManager("symbol")
market_cache = CacheManager("market")
