import json
from typing import Any
import redis.asyncio as aioredis
from app.core.config import settings

_redis: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis


async def close_redis():
    global _redis
    if _redis:
        await _redis.aclose()
        _redis = None


async def cache_get(key: str) -> Any | None:
    r = await get_redis()
    value = await r.get(key)
    return json.loads(value) if value else None


async def cache_set(key: str, value: Any, ttl_seconds: int = 300) -> None:
    r = await get_redis()
    await r.set(key, json.dumps(value), ex=ttl_seconds)


async def cache_delete(key: str) -> None:
    r = await get_redis()
    await r.delete(key)


# JWT blacklist
async def blacklist_token(jti: str, ttl_seconds: int) -> None:
    r = await get_redis()
    await r.set(f"blacklist:{jti}", "1", ex=ttl_seconds)


async def is_token_blacklisted(jti: str) -> bool:
    r = await get_redis()
    return await r.exists(f"blacklist:{jti}") > 0


# Cache key constants — never hardcode strings in routers
class CacheKeys:
    ANALYTICS_DEMAND = "analytics:demand"
    ANALYTICS_DOCTORS = "analytics:doctors"
    SPECIALTIES = "doctors:specialties"

    @staticmethod
    def analytics_region(h3_index: str) -> str:
        return f"analytics:region:{h3_index}"