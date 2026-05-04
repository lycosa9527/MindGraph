"""
Redis rate limiting for canvas-collab WebSocket join attempts.

Uses a single atomic Lua script (two sliding-window buckets checked in one
round-trip) so user and IP limits are evaluated atomically without an
intermediate read-then-write race. Aligns with the REST POST /workshop/join
limits to prevent WS-based circumvention.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
import os
import time
from typing import Optional

from fastapi import WebSocket
from redis.exceptions import RedisError

from services.infrastructure.monitoring.ws_metrics import record_ws_canvas_collab_join_rate_limited
from services.online_collab.redis.online_collab_redis_scripts import (
    RATE_LIMIT_SCRIPT_NAME,
    evalsha_with_reload,
)
from services.redis.redis_async_client import get_async_redis

logger = logging.getLogger(__name__)

_MAX_USER_ATTEMPTS = 20
_MAX_IP_ATTEMPTS = 120
_WINDOW_SECONDS = 60

_RATE_PREFIX = "rate:"

# When True (default), a Redis error during the join rate-limit check silently
# allows the join to proceed.  Set to False in production to deny joins during
# Redis outages and prevent brute-force spikes.
_FAIL_OPEN: bool = os.environ.get("COLLAB_JOIN_RL_FAIL_OPEN", "true").lower() in (
    "1", "true", "yes",
)


def _client_ip_from_websocket(websocket: WebSocket) -> str:
    """Best-effort client IP (matches HTTP proxy header priority)."""
    headers = websocket.headers
    fwd = headers.get("x-forwarded-for") or headers.get("X-Forwarded-For")
    if fwd:
        return fwd.split(",")[0].strip() or "unknown"
    real = headers.get("x-real-ip") or headers.get("X-Real-IP")
    if real:
        return real.strip() or "unknown"
    peer = websocket.client
    return peer.host if peer else "unknown"


async def check_canvas_collab_join_rate_limits(
    user_id: int,
    websocket: WebSocket,
) -> Optional[str]:
    """
    Sliding-window limits parallel to REST ``POST /workshop/join``.

    Evaluates the per-user bucket (20/min) and per-IP aggregate bucket
    (120/min) in a single atomic Redis round-trip via the combined Lua script.
    Falls back to the sequential two-call path when Redis is unavailable.

    Returns:
        Human-readable refusal message when limited, otherwise None.
    """
    ip = _client_ip_from_websocket(websocket)
    redis = get_async_redis()
    if not redis:
        if _FAIL_OPEN:
            return None
        return "Service temporarily unavailable. Please try again."

    now = time.time()
    win_start = now - _WINDOW_SECONDS
    user_key = f"{_RATE_PREFIX}api_workshop_join_ws_user:user:{user_id}"
    ip_key = f"{_RATE_PREFIX}api_workshop_join_ws_ip:ip:{ip}"

    try:
        result = await evalsha_with_reload(
            redis,
            RATE_LIMIT_SCRIPT_NAME,
            2,
            user_key,
            ip_key,
            str(now),
            str(win_start),
            str(_MAX_USER_ATTEMPTS),
            str(_MAX_IP_ATTEMPTS),
            str(_WINDOW_SECONDS),
        )
        u_ok, u_cnt, i_ok, i_cnt = int(result[0]), int(result[1]), int(result[2]), int(result[3])
    except (RedisError, OSError, TypeError, ValueError, IndexError) as exc:
        if _FAIL_OPEN:
            logger.warning("[CanvasCollabJoinRL] Rate-limit check failed (allowing): %s", exc)
            return None
        logger.warning("[CanvasCollabJoinRL] Rate-limit check failed (denying): %s", exc)
        return "Service temporarily unavailable. Please try again."

    if not u_ok:
        try:
            record_ws_canvas_collab_join_rate_limited()
        except (AttributeError, KeyError):
            pass
        logger.warning(
            "[CanvasCollabJoinRL] User limit user_id=%s count=%s/%s",
            user_id, u_cnt, _MAX_USER_ATTEMPTS,
        )
        minutes = (_WINDOW_SECONDS // 60) + 1
        return (
            f"Too many attempts ({u_cnt} in {_WINDOW_SECONDS // 60} minutes). "
            f"Please try again in {minutes} minute{'s' if minutes > 1 else ''}."
        )

    if not i_ok:
        try:
            record_ws_canvas_collab_join_rate_limited()
        except (AttributeError, KeyError):
            pass
        logger.warning(
            "[CanvasCollabJoinRL] IP limit ip=%s count=%s/%s user_id=%s",
            ip, i_cnt, _MAX_IP_ATTEMPTS, user_id,
        )
        minutes = (_WINDOW_SECONDS // 60) + 1
        return (
            f"Too many attempts ({i_cnt} in {_WINDOW_SECONDS // 60} minutes). "
            f"Please try again in {minutes} minute{'s' if minutes > 1 else ''}."
        )

    return None
