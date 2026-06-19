"""
Redis cache for per-organization Dify server health (dual-server failover).

The background heartbeat poller writes one entry per ``org_id``+``server`` with
the latest probe outcome. The MindMate credential resolver reads it to decide
whether to fail over from the primary server to the standby. Redis is the shared
source of truth across workers; a short TTL is a safety net if the poller stops.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Optional

from services.redis import keys as _keys
from services.redis.redis_async_client import get_async_redis
from services.redis.redis_client import is_redis_available
from services.utils.error_types import REDIS_ERRORS

logger = logging.getLogger(__name__)

# Consecutive failed probes before a server is treated as down (anti-flap).
HEALTH_FAILURE_THRESHOLD = 2


@dataclass(frozen=True)
class DifyServerHealth:
    """Snapshot of one Dify server's health for one organization."""

    online: bool
    consecutive_failures: int
    last_ok_at: Optional[float]
    last_checked_at: float

    @property
    def considered_down(self) -> bool:
        """True only once failures cross the anti-flap threshold."""
        return not self.online and self.consecutive_failures >= HEALTH_FAILURE_THRESHOLD


def _cache_key(org_id: int, server: int) -> str:
    """Cache key."""
    return _keys.DIFY_SERVER_HEALTH.format(org_id=int(org_id), server=int(server))


def _deserialize(text: str) -> Optional[DifyServerHealth]:
    """Deserialize."""
    try:
        raw = json.loads(text)
        if not isinstance(raw, dict):
            return None
        return DifyServerHealth(
            online=bool(raw.get("online", False)),
            consecutive_failures=int(raw.get("consecutive_failures", 0)),
            last_ok_at=raw.get("last_ok_at"),
            last_checked_at=float(raw.get("last_checked_at", 0.0)),
        )
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        logger.debug("Invalid Dify server health cache JSON: %s", exc)
        return None


async def get_server_health(org_id: int, server: int) -> Optional[DifyServerHealth]:
    """Return the cached health snapshot, or None on miss / Redis unavailable."""
    if not is_redis_available():
        return None
    redis = get_async_redis()
    if not redis:
        return None
    try:
        text = await redis.get(_cache_key(org_id, server))
    except REDIS_ERRORS as exc:
        logger.debug("Dify server health read failed: %s", exc)
        return None
    if text is None:
        return None
    if isinstance(text, bytes):
        text = text.decode("utf-8")
    return _deserialize(text)


async def record_probe_result(org_id: int, server: int, online: bool) -> DifyServerHealth:
    """
    Fold a new probe outcome into the cached snapshot and persist it.

    Reads the previous snapshot to maintain the consecutive-failure counter used
    for anti-flap hysteresis, then writes the updated snapshot back with TTL.
    """
    now = time.time()
    previous = await get_server_health(org_id, server)
    prev_failures = previous.consecutive_failures if previous else 0
    prev_last_ok = previous.last_ok_at if previous else None

    if online:
        snapshot = DifyServerHealth(
            online=True,
            consecutive_failures=0,
            last_ok_at=now,
            last_checked_at=now,
        )
    else:
        snapshot = DifyServerHealth(
            online=False,
            consecutive_failures=prev_failures + 1,
            last_ok_at=prev_last_ok,
            last_checked_at=now,
        )

    if not is_redis_available():
        return snapshot
    redis = get_async_redis()
    if not redis:
        return snapshot
    try:
        payload = json.dumps(
            {
                "online": snapshot.online,
                "consecutive_failures": snapshot.consecutive_failures,
                "last_ok_at": snapshot.last_ok_at,
                "last_checked_at": snapshot.last_checked_at,
            },
            ensure_ascii=False,
        )
        await redis.setex(_cache_key(org_id, server), _keys.TTL_DIFY_SERVER_HEALTH, payload)
    except REDIS_ERRORS as exc:
        logger.debug("Dify server health write failed: %s", exc)
    return snapshot
