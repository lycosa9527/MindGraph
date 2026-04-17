"""
Cross-worker workshop chat presence (org-scoped) using Redis sorted sets.

Scores are Unix timestamps; stale entries are removed on read.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
import time
from typing import Set

from services.redis.redis_async_client import get_async_redis

logger = logging.getLogger(__name__)

_PRESENCE_TTL_SECONDS = 90.0
_KEY_PREFIX = "mg:ws:chat:poro:"


def _key(org_id: int) -> str:
    return f"{_KEY_PREFIX}{org_id}"


async def touch_presence_org_user(org_id: int, user_id: int) -> None:
    """Record that user_id is active in presence org scope."""
    try:
        r = get_async_redis()
        if not r:
            return
        now = time.time()
        key = _key(org_id)
        async with r.pipeline(transaction=False) as pipe:
            pipe.zadd(key, {str(user_id): now})
            pipe.expire(key, int(_PRESENCE_TTL_SECONDS * 3))
            await pipe.execute()
    except Exception as exc:  # pylint: disable=broad-except
        logger.debug("[PresenceStore] touch failed: %s", exc)


async def remove_presence_org_user(org_id: int, user_id: int) -> None:
    """Remove user from org presence set (e.g. disconnect)."""
    try:
        r = get_async_redis()
        if not r:
            return
        await r.zrem(_key(org_id), str(user_id))
    except Exception as exc:  # pylint: disable=broad-except
        logger.debug("[PresenceStore] remove failed: %s", exc)


async def online_user_ids_for_org(org_id: int) -> Set[int]:
    """Return user IDs seen as online in org within the TTL window."""
    try:
        r = get_async_redis()
        if not r:
            return set()
        key = _key(org_id)
        now = time.time()
        min_score = now - _PRESENCE_TTL_SECONDS
        async with r.pipeline(transaction=False) as pipe:
            pipe.zremrangebyscore(key, 0, min_score)
            pipe.zrangebyscore(key, min_score, now + 1)
            results = await pipe.execute()
        members = results[1] if len(results) > 1 else []
        out: Set[int] = set()
        for m in members or []:
            try:
                out.add(int(m))
            except (ValueError, TypeError):
                continue
        return out
    except Exception as exc:  # pylint: disable=broad-except
        logger.debug("[PresenceStore] online_user_ids failed: %s", exc)
        return set()
