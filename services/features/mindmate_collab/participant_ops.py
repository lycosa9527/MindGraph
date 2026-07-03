"""
MindMate collab participant Redis TTL refresh (HEXPIRE with EXPIRE fallback).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
from typing import Any, Awaitable, cast

from redis.exceptions import RedisError, ResponseError

from services.features.mindmate_collab.config import MINDMATE_COLLAB_PARTICIPANTS_TTL
from services.features.mindmate_collab.redis_keys import normalize_collab_code, participants_key
from services.infrastructure.monitoring.ws_metrics import record_ws_hexpire_downgrade
from services.redis.redis_async_client import get_async_redis
from services.utils.error_types import REDIS_ERRORS

logger = logging.getLogger(__name__)


async def _hexpire_field(redis: Any, key: str, ttl: int, field: str) -> None:
    """Set per-field TTL on a HASH; fall back to whole-key EXPIRE when HEXPIRE is unavailable."""
    try:
        await redis.hexpire(key, ttl, field)
    except (ResponseError, AttributeError, TypeError):
        try:
            record_ws_hexpire_downgrade()
        except (AttributeError, TypeError, RuntimeError, OSError):
            pass
        try:
            await cast(Awaitable[Any], redis.expire(key, ttl))
        except (RedisError, OSError):
            pass


async def refresh_participant_ttl_for_code(code: str, user_id: int) -> None:
    """Slide the per-field TTL for an active MindMate collab participant."""
    redis = get_async_redis()
    if not redis:
        return
    norm = normalize_collab_code(code)
    field = str(user_id)
    p_key = participants_key(norm)
    try:
        exists = await cast(Awaitable[int], redis.hexists(p_key, field))
        if exists:
            await _hexpire_field(redis, p_key, MINDMATE_COLLAB_PARTICIPANTS_TTL, field)
    except REDIS_ERRORS as exc:
        logger.debug(
            "[MindmateCollabParticipantOps] TTL refresh failed code=%s user=%s: %s",
            norm,
            user_id,
            exc,
        )
