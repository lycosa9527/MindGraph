"""Redis cache for user-scoped API tokens (mgat_ prefix).

Key: usertoken:hash:{sha256(raw)[:32]} -> JSON {user_id, expires_at, is_active, token_hash_full}
TTL: 7 days (aligned with default token lifetime).
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


def _short_hash_from_raw_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()[:32]


def _short_hash_from_full_token_hash(token_hash_64: str) -> str:
    return token_hash_64[:32]


class _UserTokenCache:
    async def get_by_raw_token(self, raw_token: str) -> Optional[Dict[str, Any]]:
        if not is_redis_available():
            return None
        redis = get_async_redis()
        if not redis:
            return None
        sh = _short_hash_from_raw_token(raw_token)
        cache_key = _keys.USER_TOKEN_BY_HASH.format(hash=sh)
        try:
            raw = await redis.get(cache_key)
            if raw:
                return json.loads(raw)
        except Exception as exc:
            logger.debug("[UserTokenCache] get failed: %s", exc)
        return None

    async def get_by_token_hash_64(self, token_hash_64: str) -> Optional[Dict[str, Any]]:
        if not is_redis_available():
            return None
        redis = get_async_redis()
        if not redis:
            return None
        sh = _short_hash_from_full_token_hash(token_hash_64)
        cache_key = _keys.USER_TOKEN_BY_HASH.format(hash=sh)
        try:
            raw = await redis.get(cache_key)
            if raw:
                return json.loads(raw)
        except Exception as exc:
            logger.debug("[UserTokenCache] get_by_token_hash_64 failed: %s", exc)
        return None

    async def set_from_row(self, raw_token: str, row: Any) -> None:
        if not is_redis_available():
            return
        redis = get_async_redis()
        if not redis:
            return
        sh = _short_hash_from_raw_token(raw_token)
        cache_key = _keys.USER_TOKEN_BY_HASH.format(hash=sh)
        expires_at = row.expires_at
        expires_iso = expires_at.isoformat() if expires_at else None
        payload = {
            "user_id": row.user_id,
            "expires_at": expires_iso,
            "is_active": bool(row.is_active),
            "token_hash_full": row.token_hash,
        }
        try:
            await redis.setex(cache_key, _keys.TTL_USER_TOKEN, json.dumps(payload))
        except Exception as exc:
            logger.debug("[UserTokenCache] set failed: %s", exc)

    async def invalidate_by_token_hash_64(self, token_hash_64: str) -> None:
        if not is_redis_available():
            return
        redis = get_async_redis()
        if not redis:
            return
        sh = _short_hash_from_full_token_hash(token_hash_64)
        cache_key = _keys.USER_TOKEN_BY_HASH.format(hash=sh)
        try:
            await redis.delete(cache_key)
        except Exception as exc:
            logger.debug("[UserTokenCache] invalidate failed: %s", exc)

    @staticmethod
    def is_expired(cached: Dict[str, Any]) -> bool:
        expires_at_str = cached.get("expires_at")
        if not expires_at_str:
            return False
        try:
            exp = datetime.fromisoformat(expires_at_str)
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=UTC)
            return exp < datetime.now(timezone.utc)
        except (ValueError, TypeError):
            return False


user_token_cache = _UserTokenCache()
