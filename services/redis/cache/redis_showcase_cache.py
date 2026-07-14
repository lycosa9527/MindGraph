"""
Redis Showcase cache (Community-style cache-aside).

Key Schema:
- showcase:version
- showcase:list:{hash}:v{version}
- showcase:post:{post_id}
- showcase:meta
- showcase:upload_grant:{user_id}:{post_id}:{role}

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import hashlib
import logging
import time
from typing import Any, Optional

import orjson

from services.redis import keys as _keys
from services.redis.redis_async_client import get_async_redis
from services.redis.redis_client import is_redis_available
from services.utils.error_types import REDIS_ERRORS

logger = logging.getLogger(__name__)

SHOWCASE_VERSION_KEY = _keys.SHOWCASE_VERSION
LIST_TTL = _keys.TTL_SHOWCASE_LIST
POST_TTL = _keys.TTL_SHOWCASE_POST
VERSION_TTL = _keys.TTL_SHOWCASE_VERSION
META_TTL = _keys.TTL_SHOWCASE_META

# Process-local grants when Redis is unavailable (local/CI fallback).
_MEMORY_GRANTS: dict[str, tuple[float, dict[str, Any]]] = {}


def clear_memory_upload_grants() -> None:
    """Clear in-process upload-grant fallback (used by unit tests)."""
    _MEMORY_GRANTS.clear()


def _memory_grant_key(user_id: int, post_id: str, role: str) -> str:
    return _keys.SHOWCASE_UPLOAD_GRANT.format(user_id=user_id, post_id=post_id, role=role)


def _purge_expired_memory_grants() -> None:
    now = time.monotonic()
    expired = [key for key, (deadline, _) in _MEMORY_GRANTS.items() if deadline <= now]
    for key in expired:
        _MEMORY_GRANTS.pop(key, None)


def _list_cache_key(
    *,
    user_id: int,
    mine: bool,
    case_type: Optional[str],
    subject: Optional[str],
    grade: Optional[str],
    sort: str,
    page: int,
    page_size: int,
    version: int,
) -> str:
    parts = f"{user_id}:{mine}:{case_type or ''}:{subject or ''}:{grade or ''}:{sort}:{page}:{page_size}"
    h = hashlib.sha256(parts.encode()).hexdigest()[:16]
    return _keys.SHOWCASE_LIST.format(hash16=h, version=version)


async def get_version() -> int:
    """Current showcase cache version."""
    if not is_redis_available():
        return 0
    redis = get_async_redis()
    if not redis:
        return 0
    try:
        val = await redis.get(SHOWCASE_VERSION_KEY)
        return int(val) if val else 0
    except (*REDIS_ERRORS, ValueError, TypeError) as exc:
        logger.warning("[ShowcaseCache] version read failed: %s", exc)
        return 0


async def invalidate_all() -> None:
    """Bump version to invalidate all list caches."""
    if not is_redis_available():
        return
    redis = get_async_redis()
    if not redis:
        return
    try:
        async with redis.pipeline(transaction=False) as pipe:
            pipe.incr(SHOWCASE_VERSION_KEY)
            pipe.expire(SHOWCASE_VERSION_KEY, VERSION_TTL)
            await pipe.execute()
    except REDIS_ERRORS as exc:
        logger.warning("[ShowcaseCache] version incr failed: %s", exc)


async def invalidate_post(post_id: str) -> None:
    """Delete cached post and bump list version."""
    await invalidate_all()
    if not is_redis_available():
        return
    redis = get_async_redis()
    if not redis:
        return
    try:
        await redis.delete(_keys.SHOWCASE_POST.format(post_id=post_id))
    except REDIS_ERRORS as exc:
        logger.warning("[ShowcaseCache] post delete failed: %s", exc)


async def get_cached_list(
    *,
    user_id: int,
    mine: bool,
    case_type: Optional[str],
    subject: Optional[str],
    grade: Optional[str],
    sort: str,
    page: int,
    page_size: int,
) -> Optional[dict]:
    """Cache-aside list read."""
    if not is_redis_available():
        return None
    redis = get_async_redis()
    if not redis:
        return None
    version = await get_version()
    key = _list_cache_key(
        user_id=user_id,
        mine=mine,
        case_type=case_type,
        subject=subject,
        grade=grade,
        sort=sort,
        page=page,
        page_size=page_size,
        version=version,
    )
    try:
        raw = await redis.get(key)
        if not raw:
            return None
        return orjson.loads(raw)
    except REDIS_ERRORS as exc:
        logger.warning("[ShowcaseCache] list get failed: %s", exc)
        return None


async def set_cached_list(
    payload: dict,
    *,
    user_id: int,
    mine: bool,
    case_type: Optional[str],
    subject: Optional[str],
    grade: Optional[str],
    sort: str,
    page: int,
    page_size: int,
) -> None:
    """Store list response."""
    if not is_redis_available():
        return
    redis = get_async_redis()
    if not redis:
        return
    version = await get_version()
    key = _list_cache_key(
        user_id=user_id,
        mine=mine,
        case_type=case_type,
        subject=subject,
        grade=grade,
        sort=sort,
        page=page,
        page_size=page_size,
        version=version,
    )
    try:
        await redis.set(key, orjson.dumps(payload), ex=LIST_TTL)
    except REDIS_ERRORS as exc:
        logger.warning("[ShowcaseCache] list set failed: %s", exc)


async def get_cached_post(post_id: str) -> Optional[dict]:
    """Cached single post payload."""
    if not is_redis_available():
        return None
    redis = get_async_redis()
    if not redis:
        return None
    try:
        raw = await redis.get(_keys.SHOWCASE_POST.format(post_id=post_id))
        if not raw:
            return None
        return orjson.loads(raw)
    except REDIS_ERRORS as exc:
        logger.warning("[ShowcaseCache] post get failed: %s", exc)
        return None


async def set_cached_post(post_id: str, payload: dict) -> None:
    """Cache single post."""
    if not is_redis_available():
        return
    redis = get_async_redis()
    if not redis:
        return
    try:
        await redis.set(
            _keys.SHOWCASE_POST.format(post_id=post_id),
            orjson.dumps(payload),
            ex=POST_TTL,
        )
    except REDIS_ERRORS as exc:
        logger.warning("[ShowcaseCache] post set failed: %s", exc)


async def get_cached_meta() -> Optional[dict]:
    """Cached field options / tags meta."""
    if not is_redis_available():
        return None
    redis = get_async_redis()
    if not redis:
        return None
    try:
        raw = await redis.get(_keys.SHOWCASE_META)
        if not raw:
            return None
        return orjson.loads(raw)
    except REDIS_ERRORS as exc:
        logger.warning("[ShowcaseCache] meta get failed: %s", exc)
        return None


async def set_cached_meta(payload: dict) -> None:
    """Cache meta payload."""
    if not is_redis_available():
        return
    redis = get_async_redis()
    if not redis:
        return
    try:
        await redis.set(_keys.SHOWCASE_META, orjson.dumps(payload), ex=META_TTL)
    except REDIS_ERRORS as exc:
        logger.warning("[ShowcaseCache] meta set failed: %s", exc)


async def invalidate_meta() -> None:
    """Drop meta cache."""
    if not is_redis_available():
        return
    redis = get_async_redis()
    if not redis:
        return
    try:
        await redis.delete(_keys.SHOWCASE_META)
    except REDIS_ERRORS as exc:
        logger.warning("[ShowcaseCache] meta delete failed: %s", exc)


async def save_upload_grant(
    *,
    user_id: int,
    post_id: str,
    role: str,
    logical_key: str,
    content_type: str,
    max_bytes: int,
    ttl_seconds: int,
) -> None:
    """Bind a minted upload key to user+post+role for complete anti-swap checks."""
    payload = {
        "key": logical_key,
        "content_type": content_type,
        "max_bytes": max_bytes,
    }
    grant_key = _memory_grant_key(user_id, post_id, role)
    if not is_redis_available():
        _purge_expired_memory_grants()
        _MEMORY_GRANTS[grant_key] = (time.monotonic() + float(ttl_seconds), payload)
        return
    redis = get_async_redis()
    if not redis:
        _MEMORY_GRANTS[grant_key] = (time.monotonic() + float(ttl_seconds), payload)
        return
    try:
        await redis.set(grant_key, orjson.dumps(payload), ex=ttl_seconds)
    except REDIS_ERRORS as exc:
        logger.warning("[ShowcaseCache] grant save failed: %s", exc)
        _MEMORY_GRANTS[grant_key] = (time.monotonic() + float(ttl_seconds), payload)


async def pop_upload_grant(
    *,
    user_id: int,
    post_id: str,
    role: str,
) -> Optional[dict[str, Any]]:
    """Load and delete upload grant (one-shot)."""
    grant_key = _memory_grant_key(user_id, post_id, role)
    _purge_expired_memory_grants()
    mem = _MEMORY_GRANTS.pop(grant_key, None)
    if mem is not None:
        _, payload = mem
        return payload

    if not is_redis_available():
        return None
    redis = get_async_redis()
    if not redis:
        return None
    try:
        raw = await redis.get(grant_key)
        if not raw:
            return None
        await redis.delete(grant_key)
        data = orjson.loads(raw)
        return data if isinstance(data, dict) else None
    except (*REDIS_ERRORS, ValueError, TypeError) as exc:
        logger.warning("[ShowcaseCache] grant pop failed: %s", exc)
        return None
