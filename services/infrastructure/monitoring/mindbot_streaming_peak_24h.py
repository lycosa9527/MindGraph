"""Record and read cluster-wide MindBot Dify SSE streaming concurrency high-water.

Each UTC hour we store the maximum ``active_dify_streaming`` (summed across
workers) seen during admin ``/admin/performance/live`` polls, then return the
largest of the last 24 hourly values.

Copyright 2024-2026 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any, Dict, List, Optional

from services.redis import keys as redis_keys
from services.redis.redis_async_client import get_async_redis
from services.redis.redis_client import is_redis_available

logger = logging.getLogger(__name__)

_MAX_BUCKETS = 24


def _hour_tag_utc(when: datetime) -> str:
    return when.astimezone(UTC).strftime("%Y%m%d%H")


def _max_from_raw(raw: Optional[object]) -> int:
    if raw is None:
        return 0
    if isinstance(raw, (bytes, bytearray, memoryview)):
        try:
            return int(bytes(raw).decode("utf-8", errors="strict"))
        except (TypeError, ValueError, UnicodeError):
            return 0
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return int(raw)
    if isinstance(raw, str) and raw.strip():
        try:
            return int(raw.strip())
        except ValueError:
            return 0
    return 0


async def record_and_read_mindbot_streaming_peak_24h(
    cluster_streaming: int,
) -> Dict[str, Any]:
    """Update the current hour bucket; return the max of the last 24 UTC hours."""
    if not is_redis_available():
        return {"active_max_24h": None, "error": "Redis unavailable"}
    client = get_async_redis()
    if client is None:
        return {"active_max_24h": None, "error": "Async Redis not initialized"}
    now = datetime.now(UTC)
    current_tag = _hour_tag_utc(now)
    key_current = redis_keys.MINDBOT_STREAMING_HOUR_MAX.format(hour_utc=current_tag)
    new_obs = max(0, int(cluster_streaming))
    try:
        raw_old = await client.get(key_current)
    except (ConnectionError, OSError, RuntimeError, TypeError, ValueError) as exc:
        logger.debug("mindbot streaming hour get failed: %s", exc)
        return {"active_max_24h": None, "error": str(exc)}
    prev = _max_from_raw(raw_old)
    merged = max(prev, new_obs)
    if merged != prev or raw_old is None:
        try:
            await client.set(
                key_current,
                str(merged),
                ex=redis_keys.TTL_MINDBOT_STREAMING_HOUR_MAX,
            )
        except (ConnectionError, OSError, RuntimeError, TypeError, ValueError) as exc:
            logger.debug("mindbot streaming hour set failed: %s", exc)
            return {"active_max_24h": None, "error": str(exc)}
    keys: List[str] = []
    for i in range(_MAX_BUCKETS):
        tag = _hour_tag_utc(now - timedelta(hours=i))
        keys.append(redis_keys.MINDBOT_STREAMING_HOUR_MAX.format(hour_utc=tag))
    try:
        values = await client.mget(keys)
    except (ConnectionError, OSError, RuntimeError, TypeError, ValueError) as exc:
        logger.debug("mindbot streaming 24h mget failed: %s", exc)
        return {"active_max_24h": None, "error": str(exc)}
    peak = 0
    for val in values:
        peak = max(peak, _max_from_raw(val))
    return {"active_max_24h": int(peak), "error": None}
