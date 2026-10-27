"""
Cross-worker org presence using one Redis sorted set per school.

Workshop chat and MindMate notify each write their own member
(``user_id:workshop`` / ``user_id:notify``). A person stays online while
either socket is fresh. Scores are Unix timestamps; stale entries are
removed on read. A bare user id is the pre-source format and still counts
until it ages out.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
import time
from typing import Set

from services.redis.redis_async_client import get_async_redis
from services.utils.error_types import REDIS_ERRORS

logger = logging.getLogger(__name__)

PRESENCE_SOURCE_WORKSHOP = "workshop"
PRESENCE_SOURCE_NOTIFY = "notify"
_SOURCES = frozenset({PRESENCE_SOURCE_WORKSHOP, PRESENCE_SOURCE_NOTIFY})

_PRESENCE_TTL_SECONDS = 90.0
_KEY_PREFIX = "mg:ws:chat:poro:"


def _key(org_id: int) -> str:
    """Key."""
    return f"{_KEY_PREFIX}{org_id}"


def user_id_from_presence_member(raw: object) -> int | None:
    """User id from a sorted-set member, or None when the member is junk."""
    if isinstance(raw, bytes):
        text = raw.decode("utf-8", errors="ignore")
    else:
        text = str(raw)
    head = text.split(":", 1)[0]
    if not head.isdigit():
        return None
    user_id = int(head)
    if user_id <= 0:
        return None
    return user_id


def user_ids_from_presence_members(members: list) -> Set[int]:
    """Unique user ids represented by presence sorted-set members."""
    online: Set[int] = set()
    for raw in members:
        user_id = user_id_from_presence_member(raw)
        if user_id is not None:
            online.add(user_id)
    return online


def _sourced_member(user_id: int, source: str) -> str | None:
    if user_id <= 0 or source not in _SOURCES:
        return None
    return f"{user_id}:{source}"


async def touch_presence_org_user(org_id: int, user_id: int, *, source: str) -> None:
    """Record that this socket source is active in the school."""
    member = _sourced_member(user_id, source)
    if member is None:
        return
    try:
        r = get_async_redis()
        if not r:
            return
        now = time.time()
        key = _key(org_id)
        async with r.pipeline(transaction=False) as pipe:
            pipe.zadd(key, {member: now})
            pipe.zrem(key, str(user_id))
            pipe.expire(key, int(_PRESENCE_TTL_SECONDS * 3))
            await pipe.execute()
    except REDIS_ERRORS as exc:
        logger.debug("[PresenceStore] touch failed: %s", exc)


async def remove_presence_org_user(org_id: int, user_id: int, *, source: str) -> bool:
    """Drop one socket source. True when another source still keeps them online."""
    member = _sourced_member(user_id, source)
    if member is None:
        return False
    try:
        r = get_async_redis()
        if not r:
            return False
        await r.zrem(_key(org_id), member)
        return user_id in await online_user_ids_for_org(org_id)
    except REDIS_ERRORS as exc:
        logger.debug("[PresenceStore] remove failed: %s", exc)
        return False


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
        return user_ids_from_presence_members(list(members or []))
    except REDIS_ERRORS as exc:
        logger.debug("[PresenceStore] online_user_ids failed: %s", exc)
        return set()
