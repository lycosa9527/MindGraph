"""
Redis cache for the feature org/user access map (shared across workers).

Database remains source of truth. Reads try Redis first; on miss, load Postgres
and populate Redis. Admin writes refresh Redis from the in-memory payload after
commit (no stale reads). TTL is a safety net if invalidation is missed.
"""

import json
import logging
from typing import Dict, Optional

from models.domain.feature_org_access import FeatureOrgAccessEntry
from services.redis.redis_client import RedisOps, is_redis_available

logger = logging.getLogger(__name__)

CACHE_KEY = "cache:feature_org_access:v1"
CACHE_TTL_SECONDS = 86400


def _deserialize(text: str) -> Optional[Dict[str, FeatureOrgAccessEntry]]:
    try:
        raw = json.loads(text)
        if not isinstance(raw, dict):
            return None
        out: Dict[str, FeatureOrgAccessEntry] = {}
        for key, value in raw.items():
            if not isinstance(key, str):
                continue
            if not isinstance(value, dict):
                continue
            out[key] = FeatureOrgAccessEntry.model_validate(value)
        return out
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        logger.warning("Invalid feature org access cache JSON: %s", exc)
        return None


def get_cached_map() -> Optional[Dict[str, FeatureOrgAccessEntry]]:
    """
    Return the cached map if present and valid.

    Returns None on miss, Redis unavailable, or corrupt payload (key deleted).
    """
    if not is_redis_available():
        return None
    text = RedisOps.get(CACHE_KEY)
    if text is None:
        return None
    if isinstance(text, bytes):
        text = text.decode("utf-8")
    result = _deserialize(text)
    if result is None:
        RedisOps.delete(CACHE_KEY)
        return None
    return result


def set_cached_map(data: Dict[str, FeatureOrgAccessEntry]) -> None:
    """Store the map in Redis with TTL (refreshed on every admin write)."""
    if not is_redis_available():
        return
    try:
        payload = {k: v.model_dump() for k, v in data.items()}
        text = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        RedisOps.set_with_ttl(CACHE_KEY, text, CACHE_TTL_SECONDS)
    except (TypeError, ValueError) as exc:
        logger.warning("Failed to serialize feature org access cache: %s", exc)


def invalidate_cached_map() -> None:
    """Delete cache key (e.g. after manual DB repair outside the app)."""
    if not is_redis_available():
        return
    RedisOps.delete(CACHE_KEY)
