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
    """Wrapper for cache decorator — checks flag at call time, not decoration time."""
    def decorator(func):
        cached_func = cache(expire=expire)(func)
        
        async def wrapper(*args, **kwargs):
            if _cache_enabled:
                return await cached_func(*args, **kwargs)
            return await func(*args, **kwargs)
        
        wrapper.__name__ = func.__name__
        return wrapper
    return decorator