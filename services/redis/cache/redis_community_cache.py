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

import orjson

from services.redis.redis_async_client import get_async_redis
from services.redis.redis_client import is_redis_available
from services.redis import keys as _keys

logger = logging.getLogger(__name__)

COMMUNITY_VERSION_KEY = _keys.COMMUNITY_VERSION
LIST_TTL_SECONDS = _keys.TTL_COMMUNITY_LIST
POST_TTL_SECONDS = _keys.TTL_COMMUNITY_POST
VERSION_TTL_SECONDS = _keys.TTL_COMMUNITY_VERSION


def _list_cache_key(
    mine: bool,
    type_filter: Optional[str],
    category: Optional[str],
    sort: str,
    page: int,
    page_size: int,
    version: int,
) -> str:
    """Build versioned cache key for list endpoint."""
    parts = f"{mine}:{type_filter or ''}:{category or ''}:{sort}:{page}:{page_size}"
    h = hashlib.sha256(parts.encode()).hexdigest()[:16]
    return _keys.COMMUNITY_LIST.format(hash16=h, version=version)


async def get_version() -> int:
    """Get current community cache version."""
    if not is_redis_available():
        return 0
    redis = get_async_redis()
    if not redis:
        return 0
    try:
        val = await redis.get(COMMUNITY_VERSION_KEY)
        return int(val) if val else 0
    except (ValueError, TypeError):
        return 0
    except Exception as exc:
        logger.warning("[CommunityCache] Failed to read version: %s", exc)
        return 0


async def increment_version() -> None:
    """Increment version to invalidate all list caches. Non-blocking."""
    if not is_redis_available():
        return
    redis = get_async_redis()
    if not redis:
        return
    try:
        async with redis.pipeline(transaction=False) as pipe:
            pipe.incr(COMMUNITY_VERSION_KEY)
            pipe.expire(COMMUNITY_VERSION_KEY, VERSION_TTL_SECONDS)
            await pipe.execute()
        logger.debug("[CommunityCache] Version incremented")
    except Exception as exc:
        logger.warning("[CommunityCache] Failed to increment version: %s", exc)


async def get_cached_list(
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
    redis = get_async_redis()
    if not redis:
        return None
    version = await get_version()
    key = _list_cache_key(mine, type_filter, category, sort, page, page_size, version)
    try:
        raw = await redis.get(key)
    except Exception as exc:
        logger.debug("[CommunityCache] list get failed: %s", exc)
        return None
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        try:
            await redis.delete(key)
        except Exception:
            pass
        return None


async def set_cached_list(
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
    redis = get_async_redis()
    if not redis:
        return False
    version = await get_version()
    key = _list_cache_key(mine, type_filter, category, sort, page, page_size, version)
    try:
        await redis.setex(key, LIST_TTL_SECONDS, orjson.dumps(data))
        return True
    except Exception as e:
        logger.warning("[CommunityCache] Failed to cache list: %s", e)
        return False


async def get_cached_post(post_id: str) -> Optional[dict]:
    """Get cached single post. Returns None on miss or error."""
    if not is_redis_available():
        return None
    redis = get_async_redis()
    if not redis:
        return None
    key = _keys.COMMUNITY_POST.format(post_id=post_id)
    try:
        raw = await redis.get(key)
    except Exception as exc:
        logger.debug("[CommunityCache] post get failed: %s", exc)
        return None
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        try:
            await redis.delete(key)
        except Exception:
            pass
        return None


async def set_cached_post(post_id: str, data: dict) -> bool:
    """Cache single post. Non-blocking."""
    if not is_redis_available():
        return False
    redis = get_async_redis()
    if not redis:
        return False
    key = _keys.COMMUNITY_POST.format(post_id=post_id)
    try:
        await redis.setex(key, POST_TTL_SECONDS, orjson.dumps(data))
        return True
    except Exception as e:
        logger.warning("[CommunityCache] Failed to cache post %s: %s", post_id, e)
        return False


async def invalidate_post(post_id: str) -> None:
    """Invalidate cached post on update/delete."""
    if not is_redis_available():
        return
    redis = get_async_redis()
    if not redis:
        return
    key = _keys.COMMUNITY_POST.format(post_id=post_id)
    try:
        await redis.delete(key)
        logger.debug("[CommunityCache] Invalidated post %s", post_id)
    except Exception as exc:
        logger.warning("[CommunityCache] Failed to invalidate post %s: %s", post_id, exc)


async def invalidate_all() -> None:
    """Invalidate all list caches by bumping version."""
    await increment_version()
