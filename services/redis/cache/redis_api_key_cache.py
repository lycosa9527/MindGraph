"""Redis API Key Cache Service.

Cache-aside pattern for API key validation.

Key schema:
- apikey:hash:{sha256_prefix} -> JSON-serialised APIKey fields, TTL 5 min
- apikey:usage:{key_id}       -> INCR counter (flushed to Postgres periodically)

Reduces Postgres load on the hot path: validate + track usage → 3 DB queries
per authenticated request → 0–1 DB queries (miss only) + 1 Redis INCR.
"""

import hashlib
import json
import logging
from datetime import UTC, datetime, timezone
from typing import Any, Dict, Optional

from services.redis import keys as _keys
from services.redis.redis_async_client import get_async_redis
from services.redis.redis_client import is_redis_available

logger = logging.getLogger(__name__)


def _key_hash(api_key: str) -> str:
    """Return a stable, safe Redis key fragment for ``api_key``."""
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:32]


def _serialize(key_record: Any) -> str:
    """Serialize an APIKey ORM row to JSON."""
    expires_at = None
    if key_record.expires_at:
        expires_at = key_record.expires_at.isoformat()
    return json.dumps(
        {
            "id": key_record.id,
            "key": key_record.key,
            "name": key_record.name,
            "is_active": key_record.is_active,
            "quota_limit": key_record.quota_limit,
            "usage_count": key_record.usage_count,
            "expires_at": expires_at,
        }
    )


class _APIKeyCache:
    """Thin Redis cache wrapper for APIKey records."""

    async def get(self, api_key: str) -> Optional[Dict]:
        """Return cached APIKey dict or None on cache miss / Redis unavailable."""
        if not is_redis_available():
            return None
        redis = get_async_redis()
        if not redis:
            return None
        cache_key = _keys.API_KEY_BY_HASH.format(hash=_key_hash(api_key))
        try:
            raw = await redis.get(cache_key)
            if raw:
                return json.loads(raw)
        except Exception as exc:
            logger.debug("[APIKeyCache] get failed: %s", exc)
        return None

    async def set(self, api_key: str, key_record: Any) -> None:
        """Cache an APIKey row with TTL = TTL_API_KEY."""
        if not is_redis_available():
            return
        redis = get_async_redis()
        if not redis:
            return
        cache_key = _keys.API_KEY_BY_HASH.format(hash=_key_hash(api_key))
        try:
            await redis.setex(cache_key, _keys.TTL_API_KEY, _serialize(key_record))
        except Exception as exc:
            logger.debug("[APIKeyCache] set failed: %s", exc)

    async def invalidate(self, api_key: str) -> None:
        """Evict a specific key from the cache (on revoke / rotate / quota change)."""
        if not is_redis_available():
            return
        redis = get_async_redis()
        if not redis:
            return
        cache_key = _keys.API_KEY_BY_HASH.format(hash=_key_hash(api_key))
        try:
            await redis.delete(cache_key)
        except Exception as exc:
            logger.debug("[APIKeyCache] invalidate failed: %s", exc)

    async def incr_usage(self, key_id: int) -> int:
        """Atomically increment usage counter for ``key_id``.

        Returns the new counter value so callers can decide when to flush to
        Postgres.  Returns 0 if Redis is unavailable.

        Sets a safety TTL (12× cache TTL) on first increment so the key is
        self-cleaning even if the background flush job is never scheduled.
        """
        if not is_redis_available():
            return 0
        redis = get_async_redis()
        if not redis:
            return 0
        usage_key = _keys.API_KEY_USAGE_INCR.format(key_id=key_id)
        try:
            async with redis.pipeline(transaction=False) as pipe:
                pipe.incr(usage_key)
                pipe.expire(usage_key, _keys.TTL_API_KEY * 12, nx=True)
                results = await pipe.execute()
            return int(results[0])
        except Exception as exc:
            logger.debug("[APIKeyCache] incr_usage failed: %s", exc)
            return 0

    async def get_usage_delta(self, key_id: int) -> int:
        """Read and reset the pending usage delta for ``key_id``.

        Used by the background flush job to drain the Redis counter into
        Postgres atomically (GETDEL).  Returns 0 on any failure.
        """
        if not is_redis_available():
            return 0
        redis = get_async_redis()
        if not redis:
            return 0
        usage_key = _keys.API_KEY_USAGE_INCR.format(key_id=key_id)
        try:
            raw = await redis.getdel(usage_key)
            return int(raw) if raw else 0
        except Exception as exc:
            logger.debug("[APIKeyCache] get_usage_delta failed: %s", exc)
            return 0

    @staticmethod
    def is_expired(cached: Dict) -> bool:
        """Return True if the cached record is logically expired (expires_at check)."""
        expires_at_str = cached.get("expires_at")
        if not expires_at_str:
            return False
        try:
            expires_at = datetime.fromisoformat(expires_at_str)
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)
            return expires_at < datetime.now(timezone.utc)
        except (ValueError, TypeError):
            return False


api_key_cache = _APIKeyCache()
