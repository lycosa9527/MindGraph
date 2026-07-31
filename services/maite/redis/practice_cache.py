"""
Maite practice list Redis cache.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from services.redis import keys
from services.redis.redis_async_client import get_async_redis
from services.utils.error_types import JSON_PARSE_ERRORS, REDIS_ERRORS

logger = logging.getLogger(__name__)


async def get_recent_practice(user_id: int) -> Optional[list[dict[str, Any]]]:
    """Return cached recent practice entries for a user."""
    try:
        redis = get_async_redis()
        if not redis:
            return None
        raw = await redis.get(keys.MAITE_PRACTICE.format(user_id=user_id))
        if not raw:
            return None
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return parsed
    except (*REDIS_ERRORS, *JSON_PARSE_ERRORS) as exc:
        logger.debug("[MaitePracticeCache] get failed user=%s: %s", user_id, exc)
    return None


async def set_recent_practice(user_id: int, entries: list[dict[str, Any]]) -> None:
    """Store recent practice entries with TTL."""
    try:
        redis = get_async_redis()
        if not redis:
            return
        key = keys.MAITE_PRACTICE.format(user_id=user_id)
        await redis.set(key, json.dumps(entries, ensure_ascii=False), ex=keys.TTL_MAITE_PRACTICE)
    except (*REDIS_ERRORS,) as exc:
        logger.debug("[MaitePracticeCache] set failed user=%s: %s", user_id, exc)


async def invalidate_recent_practice(user_id: int) -> None:
    """Drop cached recent practice for a user."""
    try:
        redis = get_async_redis()
        if not redis:
            return
        await redis.delete(keys.MAITE_PRACTICE.format(user_id=user_id))
    except (*REDIS_ERRORS,) as exc:
        logger.debug("[MaitePracticeCache] invalidate failed user=%s: %s", user_id, exc)
