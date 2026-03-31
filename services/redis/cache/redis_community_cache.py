"""
Redis Community Cache Service
==============================

Cache-aside pattern for community list and post reads.
Reduces DB load under high concurrency.

- List cache: only when unauthenticated (is_liked always false)
- Post cache: single post by ID
- Invalidation: version bump on write; post key delete on update/delete

Key Schema:
- community:version -> Integer (incremented on any write)
- community:list:{hash}:v{version} -> JSON list response, TTL 60s
- community:post:{post_id} -> JSON post response, TTL 300s

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import hashlib
import json
import logging
from typing import Optional

from services.redis.redis_client import RedisOps, get_redis, is_redis_available

logger = logging.getLogger(__name__)

COMMUNITY_VERSION_KEY = "community:version"
COMMUNITY_LIST_PREFIX = "community:list:"
COMMUNITY_POST_PREFIX = "community:post:"
LIST_TTL_SECONDS = 60
POST_TTL_SECONDS = 300
VERSION_TTL_SECONDS = 86400  # 24 h safety net; refreshed on every increment


def _list_cache_key(
    mine: bool,
    type_filter: Optional[str],
    category: Optional[str],
    sort: str,
    page: int,
    page_size: int,
) -> str:
    """Build cache key for list endpoint."""
    parts = f"{mine}:{type_filter or ''}:{category or ''}:{sort}:{page}:{page_size}"
    h = hashlib.sha256(parts.encode()).hexdigest()[:16]
    return f"{COMMUNITY_LIST_PREFIX}{h}"


def get_version() -> int:
    """Get current community cache version."""
    if not is_redis_available():
        return 0
    redis = get_redis()
    if not redis:
        return 0
    try:
        val = redis.get(COMMUNITY_VERSION_KEY)
        return int(val) if val else 0
    except (ValueError, TypeError):
        return 0


def increment_version() -> None:
    """Increment version to invalidate all list caches. Non-blocking."""
    if not is_redis_available():
        return
    redis = get_redis()
    if not redis:
        return
    try:
        pipe = redis.pipeline()
        pipe.incr(COMMUNITY_VERSION_KEY)
        pipe.expire(COMMUNITY_VERSION_KEY, VERSION_TTL_SECONDS)
        pipe.execute()
        logger.debug("[CommunityCache] Version incremented")
    except Exception as exc:
        logger.warning("[CommunityCache] Failed to increment version: %s", exc)


def get_cached_list(
    mine: bool,
    type_filter: Optional[str],
    category: Optional[str],
    sort: str,
    page: int,
    page_size: int,
) -> Optional[dict]:
    """
    Get cached list response. Only valid when unauthenticated (mine=False).
    Returns None on miss or error.
    """
    if mine or not is_redis_available():
        return None
    version = get_version()
    key = f"{_list_cache_key(mine, type_filter, category, sort, page, page_size)}:v{version}"
    raw = RedisOps.get(key)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        RedisOps.delete(key)
        return None


def set_cached_list(
    mine: bool,
    type_filter: Optional[str],
    category: Optional[str],
    sort: str,
    page: int,
    page_size: int,
    data: dict,
) -> bool:
    """Cache list response. Non-blocking. Returns True on success."""
    if mine or not is_redis_available():
        return False
    version = get_version()
    key = f"{_list_cache_key(mine, type_filter, category, sort, page, page_size)}:v{version}"
    try:
        return RedisOps.set_with_ttl(key, json.dumps(data), LIST_TTL_SECONDS)
    except Exception as e:
        logger.warning("[CommunityCache] Failed to cache list: %s", e)
        return False


def get_cached_post(post_id: str) -> Optional[dict]:
    """Get cached single post. Returns None on miss or error."""
    if not is_redis_available():
        return None
    key = f"{COMMUNITY_POST_PREFIX}{post_id}"
    raw = RedisOps.get(key)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        RedisOps.delete(key)
        return None


def set_cached_post(post_id: str, data: dict) -> bool:
    """Cache single post. Non-blocking."""
    if not is_redis_available():
        return False
    key = f"{COMMUNITY_POST_PREFIX}{post_id}"
    try:
        return RedisOps.set_with_ttl(key, json.dumps(data), POST_TTL_SECONDS)
    except Exception as e:
        logger.warning("[CommunityCache] Failed to cache post %s: %s", post_id, e)
        return False


def invalidate_post(post_id: str) -> None:
    """Invalidate cached post on update/delete."""
    if not is_redis_available():
        return
    key = f"{COMMUNITY_POST_PREFIX}{post_id}"
    RedisOps.delete(key)
    logger.debug("[CommunityCache] Invalidated post %s", post_id)


def invalidate_all() -> None:
    """Invalidate all list caches by bumping version."""
    increment_version()
