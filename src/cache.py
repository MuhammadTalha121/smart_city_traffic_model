"""Redis caching setup for FastAPI endpoints."""

from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from fastapi_cache.decorator import cache
import redis.asyncio as redis
from src.config import REDIS_URL, CACHE_ENABLED

# Use a local flag that can be modified at runtime
_cache_enabled = CACHE_ENABLED


async def init_cache():
    """Initialize Redis cache if enabled."""
    global _cache_enabled

    if not _cache_enabled:
        print("[Cache] Cache disabled by configuration")
        return

    try:
        redis_client = redis.from_url(REDIS_URL)
        await redis_client.ping()  # test connection
        FastAPICache.init(RedisBackend(redis_client), prefix="fastapi-cache")
        print("[Cache] Redis cache initialized")
    except Exception as e:
        print(f"[Cache] Failed to initialize Redis: {e}. Running without cache.")
        _cache_enabled = False


def cached(expire: int = 60):
    """Wrapper for cache decorator with consistent naming."""
    if _cache_enabled:
        return cache(expire=expire)
    else:
        # No-op decorator
        def decorator(func):
            return func
        return decorator