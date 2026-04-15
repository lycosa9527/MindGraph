"""Per-org sliding-window rate limiter backed by Redis INCR.

Each inbound message increments a Redis counter for the org. If the counter
exceeds the configured limit within the window, the request is rejected before
reaching the Dify semaphore. This prevents one noisy org from starving others.

When Redis is unavailable the limiter fails open (returns True / "allowed") so
that a Redis outage does not bring down message processing.

Configuration (env vars)
------------------------
MINDBOT_RATE_LIMIT_ENABLED       default False  (opt-in)
MINDBOT_ORG_RATE_LIMIT           default 60     (requests per window)
MINDBOT_ORG_RATE_WINDOW_SECONDS  default 60     (window size in seconds)
"""

from __future__ import annotations

import functools
import logging

from services.mindbot.infra.redis_async import redis_incr_with_ttl
from utils.env_helpers import env_bool, env_int

logger = logging.getLogger(__name__)

_RATE_LIMIT_KEY_PREFIX = "mindbot:rate:"


@functools.cache
def _rate_limit_enabled() -> bool:
    return env_bool("MINDBOT_RATE_LIMIT_ENABLED", False)


@functools.cache
def _rate_limit_max() -> int:
    return max(1, env_int("MINDBOT_ORG_RATE_LIMIT", 60))


@functools.cache
def _rate_limit_window_seconds() -> int:
    return max(1, env_int("MINDBOT_ORG_RATE_WINDOW_SECONDS", 60))


async def check_org_rate_limit(org_id: int) -> bool:
    """
    Return True if the request is within the org's rate limit, False if rejected.

    Uses a Redis INCR + EXPIRE sliding counter.  The TTL is refreshed on every
    increment so the window slides with activity (count resets after
    ``_rate_limit_window_seconds`` of inactivity).

    Fails open when Redis is unavailable (returns True).
    """
    if not _rate_limit_enabled():
        return True

    key = f"{_RATE_LIMIT_KEY_PREFIX}{org_id}"
    window = _rate_limit_window_seconds()
    count = await redis_incr_with_ttl(key, window)
    if count is None:
        return True

    limit = _rate_limit_max()
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
