"""Per-org fixed-window rate limiter backed by Redis INCR with in-memory fallback.

Each inbound message increments a Redis counter for the org. If the counter
exceeds the configured limit within the window, the request is rejected before
reaching the Dify semaphore. This prevents one noisy org from starving others.

When Redis is unavailable the limiter falls back to a per-process in-memory
counter so abuse protection is maintained even during Redis outages.

Multi-worker caveat (in-memory fallback)
-----------------------------------------
The in-memory fallback is **per-process only**.  Under N Uvicorn workers, each
worker tracks its own counter independently, so during a Redis outage an org
can send up to N × limit requests before being blocked.  This is an acceptable
degradation compared to the alternative (no protection at all) but operators
should be aware that Redis availability is critical for globally-accurate limits.

Additionally, when ``_mem_counters`` exceeds ``MINDBOT_RATE_LIMIT_MEM_MAX_KEYS``
the oldest entries are evicted. An evicted org briefly loses its counter and may
not be accurately limited for the remainder of that window.

Configuration (env vars)
------------------------
MINDBOT_RATE_LIMIT_ENABLED       default True
MINDBOT_ORG_RATE_LIMIT           default 200    (requests per window)
MINDBOT_ORG_RATE_WINDOW_SECONDS  default 60     (window size in seconds)
MINDBOT_RATE_LIMIT_MEM_MAX_KEYS  default 5000   (max in-memory counter entries;
                                  expired entries purged when exceeded)

Operational guidance (multi-school deployments)
------------------------------------------------
**Sizing MINDBOT_ORG_RATE_LIMIT for multiple workers:**
Redis is the source of truth when available.  During a Redis outage, each
Uvicorn worker tracks its own counter independently, so the effective limit
becomes N × MINDBOT_ORG_RATE_LIMIT where N is the worker count.  To maintain
accurate protection in the worst case, set::

    MINDBOT_ORG_RATE_LIMIT = desired_hard_limit // N_WORKERS

For example, with 4 workers and a desired cluster-wide limit of 200 req/min,
set MINDBOT_ORG_RATE_LIMIT=50.  When Redis is healthy the counter accumulates
across all workers giving the correct global limit of 200; during a Redis
outage the per-process fallback allows up to 4 × 50 = 200 in the worst case
(each worker permits 50 independently), which is equivalent to the desired
limit.

**Monitoring:**
- Alert when Redis becomes unavailable (look for log lines containing
  ``rate_limit_fallback_memory``).
- Alert when any org is rate-limited (``rate_limit_exceeded``) to detect
  unusual burst traffic early.
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
def _mem_max_keys() -> int:
    return max(100, env_int("MINDBOT_RATE_LIMIT_MEM_MAX_KEYS", 5000))


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
    else:
        count = entry[0] + 1
        _mem_counters[org_id] = (count, entry[1])

    if len(_mem_counters) > _mem_max_keys():
        expired_keys = [k for k, (_, start) in _mem_counters.items() if (now - start) >= window]
        for k in expired_keys:
            del _mem_counters[k]
        if len(_mem_counters) > _mem_max_keys():
            excess = len(_mem_counters) - _mem_max_keys()
            keys_to_drop = list(_mem_counters.keys())[:excess]
            for k in keys_to_drop:
                del _mem_counters[k]
            logger.warning(
                "[MindBot] rate_limit_mem_evicted count=%s (max_keys=%s reached)",
                excess,
                _mem_max_keys(),
            )

    result = _mem_counters.get(org_id)
    return result[0] if result is not None else 1


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
        logger.warning(
            "[MindBot] rate_limit_fallback_memory org_id=%s count=%s "
            "(Redis unavailable — limit is per-process only; effective limit may be "
            "N×%s under N workers)",
            org_id,
            count,
            _rate_limit_max(),
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
