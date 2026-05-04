"""
Workshop participant Redis lifecycle operations.

Participants are stored as a Redis HASH (field=user_id, value=join-epoch-seconds)
so that Redis 7.4+ HEXPIRE can maintain per-field TTL.  When HEXPIRE is
unavailable the whole-key EXPIRE is used as a fallback, preserving backward
compatibility with older Redis deployments.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
from typing import Any, Awaitable, List, cast

from redis.exceptions import RedisError, ResponseError

from services.redis.redis_async_client import get_async_redis
from services.infrastructure.monitoring.ws_metrics import record_ws_hexpire_downgrade
from services.online_collab.spec.online_collab_live_spec_ops import maybe_flush_live_spec_when_room_empty
from services.online_collab.spec.online_collab_live_flush import schedule_live_spec_db_flush
from services.online_collab.redis.online_collab_redis_keys import (
    code_to_diagram_key,
    mutation_idle_key,
    participants_key,
)

logger = logging.getLogger(__name__)

ONLINE_COLLAB_PARTICIPANTS_TTL = 3600


async def _hexpire_field(redis: Any, key: str, ttl: int, field: str) -> None:
    """
    Set per-field TTL on a HASH using HEXPIRE (Redis 7.4+).

    Falls back to a whole-key EXPIRE when HEXPIRE is not supported so older
    Redis deployments still work correctly.
    """
    try:
        await redis.hexpire(key, ttl, field)
    except (ResponseError, AttributeError, TypeError):
        try:
            record_ws_hexpire_downgrade()
        except Exception:
            pass
        try:
            await cast(Awaitable[Any], redis.expire(key, ttl))
        except (RedisError, OSError):
            pass


async def participant_count_for_code(code: str) -> int:
    """Return the current participant count for a workshop code."""
    redis = get_async_redis()
    if not redis:
        return 0
    try:
        count = await cast(Awaitable[int], redis.hlen(participants_key(code)))
        return count if count else 0
    except (RedisError, OSError, TypeError, ValueError):
        return 0


async def get_participants_for_code(code: str) -> List[int]:
    """
    Return participant user IDs for a workshop.

    Returns:
        List of user IDs (empty list on Redis unavailability or error).
    """
    redis = get_async_redis()
    if not redis:
        logger.error("[OnlineCollabParticipantOps] Redis client not available")
        return []
    try:
        fields = await cast(Awaitable[Any], redis.hkeys(participants_key(code)))
        if not fields:
            return []
        return [
            int(f) if isinstance(f, str) else int(f.decode("utf-8"))
            for f in fields
        ]
    except (RedisError, OSError) as exc:
        logger.error(
            "[OnlineCollabParticipantOps] Error getting participants: %s",
            exc,
            exc_info=True,
        )
        return []


async def refresh_participant_ttl_for_code(code: str, user_id: int) -> None:
    """Slide the per-field TTL for an active participant using HEXPIRE."""
    redis = get_async_redis()
    if not redis:
        logger.error("[OnlineCollabParticipantOps] Redis client not available")
        return
    try:
        p_key = participants_key(code)
        field = str(user_id)
        exists = await cast(Awaitable[int], redis.hexists(p_key, field))
        if exists:
            await _hexpire_field(redis, p_key, ONLINE_COLLAB_PARTICIPANTS_TTL, field)
            logger.debug(
                "[OnlineCollabParticipantOps] Refreshed TTL for participant %s in workshop %s",
                user_id,
                code,
            )
    except (RedisError, OSError) as exc:
        logger.error(
            "[OnlineCollabParticipantOps] Error refreshing participant TTL: %s",
            exc,
            exc_info=True,
        )


async def remove_participant_from_online_collab(code: str, user_id: int) -> None:
    """
    Remove a participant from the workshop participant HASH and trigger a
    live-spec flush.  Flushes on every disconnect (not just on empty-room) so
    the DB stays current for guest reconnect scenarios where the next page load
    reads from Postgres before the WebSocket snapshot arrives.
    """
    redis = get_async_redis()
    if not redis:
        logger.error("[OnlineCollabParticipantOps] Redis client not available")
        return
    try:
        p_key = participants_key(code)
        await cast(Awaitable[Any], redis.hdel(p_key, str(user_id)))
        await cast(Awaitable[Any], redis.delete(mutation_idle_key(code, user_id)))
        async with redis.pipeline(transaction=False) as pipe:
            pipe.hlen(p_key)
            pipe.get(code_to_diagram_key(code))
            count_after, raw_did = await pipe.execute()
        if raw_did:
            diagram_id_val = raw_did if isinstance(raw_did, str) else raw_did.decode("utf-8")
            await schedule_live_spec_db_flush(code, diagram_id_val)
        await maybe_flush_live_spec_when_room_empty(redis, code)
        logger.debug(
            "[OnlineCollabParticipantOps] Removed participant %s from workshop %s "
            "count_after=%s",
            user_id,
            code,
            count_after,
        )
        from services.online_collab.core.online_collab_manager import (
            get_online_collab_manager,
        )
        await get_online_collab_manager().touch_leave(code)
    except (RedisError, OSError) as exc:
        logger.error(
            "[OnlineCollabParticipantOps] Error removing participant: %s",
            exc,
            exc_info=True,
        )
