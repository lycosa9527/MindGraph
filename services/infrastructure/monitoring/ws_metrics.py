"""
Lightweight counters for WebSocket operations (multi-worker safe via atomic Redis).

Used for operations visibility; not a full Prometheus stack.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict

from services.redis.redis_async_client import get_async_redis

logger = logging.getLogger(__name__)

_local: Dict[str, int] = {
    "ws_chat_connections": 0,
    "ws_workshop_connections": 0,
    "ws_fanout_chat_published": 0,
    "ws_fanout_chat_received": 0,
    "ws_fanout_workshop_published": 0,
    "ws_fanout_workshop_received": 0,
    "ws_auth_failures": 0,
    "ws_rate_limit_hits": 0,
}


def _bump(key: str, delta: int = 1) -> None:
    """Increment a named in-process counter.

    CPython's GIL makes simple dict integer updates atomic; no lock required
    in a single-threaded asyncio process.
    """
    _local[key] = _local.get(key, 0) + delta


def record_ws_chat_connection_delta(delta: int) -> None:
    """Adjust the per-process workshop chat WebSocket connection counter."""
    _bump("ws_chat_connections", delta)


def record_ws_workshop_connection_delta(delta: int) -> None:
    """Adjust the per-process diagram workshop WebSocket connection counter."""
    _bump("ws_workshop_connections", delta)


def record_ws_fanout_chat_published() -> None:
    """Count a chat message published to Redis fan-out."""
    _bump("ws_fanout_chat_published")


def record_ws_fanout_chat_received() -> None:
    """Count a chat fan-out message received from Redis on this worker."""
    _bump("ws_fanout_chat_received")


def record_ws_fanout_workshop_published() -> None:
    """Count a workshop message published to Redis fan-out."""
    _bump("ws_fanout_workshop_published")


def record_ws_fanout_workshop_received() -> None:
    """Count a workshop fan-out message received from Redis on this worker."""
    _bump("ws_fanout_workshop_received")


def record_ws_auth_failure() -> None:
    """Count a WebSocket authentication rejection."""
    _bump("ws_auth_failures")


def record_ws_rate_limit_hit() -> None:
    """Count a WebSocket per-connection rate limit hit."""
    _bump("ws_rate_limit_hits")


async def get_ws_metrics_snapshot() -> Dict[str, Any]:
    """Return a copy of in-process WebSocket counters plus optional Redis gauge."""
    snap = dict(_local)
    snap["timestamp"] = time.time()
    try:
        r = get_async_redis()
        if r:
            raw = await r.get("mg:ws:metrics:active_total")
            if raw is not None:
                snap["ws_active_total_redis"] = int(raw)
    except (ValueError, TypeError, Exception) as exc:  # pylint: disable=broad-except
        logger.debug("[WSMetrics] Redis gauge read failed: %s", exc)
    return snap


async def redis_increment_active_total(delta: int) -> None:
    """Best-effort global active WebSocket count in Redis (all workers)."""
    try:
        r = get_async_redis()
        if not r:
            return
        key = "mg:ws:metrics:active_total"
        async with r.pipeline() as pipe:
            pipe.incrby(key, delta)
            pipe.expire(key, 86400)
            await pipe.execute()
    except Exception as exc:  # pylint: disable=broad-except
        logger.debug("[WSMetrics] Redis increment failed: %s", exc)
