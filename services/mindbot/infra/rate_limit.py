"""Per-org fixed-window rate limiter backed by Redis INCR with in-memory fallback.

Each inbound message increments a Redis counter for the org. If the counter
exceeds the configured limit within the window, the request is rejected before
reaching the Dify semaphore. This prevents one noisy org from starving others.

When Redis is unavailable the limiter falls back to a per-process in-memory
counter so abuse protection is maintained even during Redis outages.

Configuration (env vars)
------------------------
MINDBOT_RATE_LIMIT_ENABLED       default True
MINDBOT_ORG_RATE_LIMIT           default 200    (requests per window)
MINDBOT_ORG_RATE_WINDOW_SECONDS  default 60     (window size in seconds)
"""

from __future__ import annotations

import functools
import logging
import time
from typing import Dict, Tuple

from services.mindbot.infra.redis_async import redis_incr_fixed_window
from utils.env_helpers import env_bool, env_int

logger = logging.getLogger(__name__)

_RATE_LIMIT_KEY_PREFIX = "mindbot:rate:"

_mem_counters: Dict[int, Tuple[int, float]] = {}


@functools.cache
def _rate_limit_enabled() -> bool:
    return env_bool("MINDBOT_RATE_LIMIT_ENABLED", True)


@functools.cache
def _rate_limit_max() -> int:
    return max(1, env_int("MINDBOT_ORG_RATE_LIMIT", 200))


@functools.cache
def _rate_limit_window_seconds() -> int:
    return max(1, env_int("MINDBOT_ORG_RATE_WINDOW_SECONDS", 60))


def _mem_incr(org_id: int, window: int) -> int:
    """Per-process in-memory fixed-window counter (fallback when Redis is down)."""
    now = time.monotonic()
    entry = _mem_counters.get(org_id)
    if entry is None or (now - entry[1]) >= window:
        _mem_counters[org_id] = (1, now)
        return 1
    count = entry[0] + 1
    _mem_counters[org_id] = (count, entry[1])
    return count


async def check_org_rate_limit(org_id: int) -> bool:
    """
    Return True if the request is within the org's rate limit, False if rejected.

    Uses a Redis fixed-window counter.  The TTL is set only when the key is
    first created and is never refreshed, so the counter resets after the
    window expires regardless of activity volume.

    Falls back to a per-process in-memory counter when Redis is unavailable
    so abuse protection is maintained during Redis outages.
    """
    if not _rate_limit_enabled():
        return True

    key = f"{_RATE_LIMIT_KEY_PREFIX}{org_id}"
    window = _rate_limit_window_seconds()
    limit = _rate_limit_max()

    count = await redis_incr_fixed_window(key, window)
    if count is None:
        count = _mem_incr(org_id, window)
        logger.debug(
            "[MindBot] rate_limit_fallback_memory org_id=%s count=%s",
            org_id,
            count,
        )

    if count > limit:
        logger.warning(
            "[MindBot] rate_limit_exceeded org_id=%s count=%s limit=%s window_s=%s",
            org_id,
            count,
            limit,
            window,
        )
        return False
    return True
