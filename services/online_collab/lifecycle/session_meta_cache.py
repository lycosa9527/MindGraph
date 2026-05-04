"""
Process-local session_meta HASH cache with short TTL.

The collab hot path reads ``session_meta`` on every join handshake, every
cleanup evaluation, and every idle poll. Each read is a Redis HGET(ALL) —
cheap individually but high-frequency at scale. This module wraps those
reads with a small in-process TTL cache to absorb repeated lookups without
paying a round-trip.

Design constraints
------------------
1. The cache MUST be tolerant of stale reads on the order of
   ``_DEFAULT_SESSION_META_TTL_SEC`` seconds. Callers that need strict
   consistency (e.g., cleanup race) must call ``invalidate_session_meta``
   after any write.
2. When the opt-in ``COLLAB_REDIS_CLIENT_TRACKING=1`` flag is set, the cache
   also registers RESP3 push invalidation handlers on the shared Redis
   connection so remote writes push-invalidate the local entry. This turns
   the cache from "eventually consistent within TTL" into "pointer-update
   fresh", at the cost of one CLIENT TRACKING registration per worker.

Copyright 2024-2025 Beijing Siyuan Zhijiao Technology Co., Ltd.
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
import os
import time
from collections import OrderedDict
from typing import Any, Awaitable, Dict, Optional, cast

from redis.exceptions import RedisError

from services.redis.redis_async_client import get_async_redis
from services.online_collab.redis.online_collab_redis_keys import session_meta_key

logger = logging.getLogger(__name__)

_DEFAULT_SESSION_META_TTL_SEC = 5.0
_CACHE_MAX_ENTRIES = 10_000
_CACHE_EVICT_COUNT = 500
_cache: OrderedDict[str, tuple[Dict[str, str], float]] = OrderedDict()


class _TrackingState:
    """Module-private CLIENT TRACKING registration flag."""

    registered: bool = False


def _client_tracking_enabled() -> bool:
    return os.getenv("COLLAB_REDIS_CLIENT_TRACKING", "0") not in (
        "0", "false", "False", "",
    )


def _decode(val: Any) -> str:
    if isinstance(val, bytes):
        return val.decode("utf-8", errors="replace")
    return str(val) if val is not None else ""


async def _register_client_tracking(redis: Any) -> bool:
    """
    Best-effort ``CLIENT TRACKING ON BCAST`` covering all collab key prefixes.

    Registers ``workshop:sessionmeta:`` and ``workshop:registry:`` so that
    remote writes to either namespace push-invalidate local cache entries.
    Returns True on success; callers fall back to TTL-only mode on False.
    """
    if _TrackingState.registered:
        return True
    try:
        await redis.execute_command(
            "CLIENT", "TRACKING", "ON",
            "BCAST",
            "PREFIX", "workshop:sessionmeta:",
            "PREFIX", "workshop:registry:",
        )
        _TrackingState.registered = True
        logger.info(
            "[SessionMetaCache] CLIENT TRACKING BCAST registered for "
            "workshop:sessionmeta: and workshop:registry:"
        )
        return True
    except RedisError as exc:
        logger.info(
            "[SessionMetaCache] CLIENT TRACKING unavailable (%s) — "
            "falling back to TTL-only cache", exc,
        )
        return False


async def get_session_meta_cached(
    code: str,
    ttl_sec: float = _DEFAULT_SESSION_META_TTL_SEC,
) -> Optional[Dict[str, str]]:
    """
    Read ``session_meta_key(code)`` with a short TTL cache.

    Returns ``None`` when the HASH does not exist (session expired or never
    created) and an empty dict when the HASH exists but is empty. Callers
    must not mutate the returned dict — it may be shared across call sites.
    """
    if not code:
        return None
    now = time.monotonic()
    entry = _cache.get(code)
    if entry is not None and (now - entry[1]) < ttl_sec:
        return entry[0]

    redis = get_async_redis()
    if not redis:
        return entry[0] if entry is not None else None

    if _client_tracking_enabled():
        await _register_client_tracking(redis)

    try:
        raw = await cast(
            Awaitable[Any],
            redis.hgetall(session_meta_key(code)),
        )
    except (RedisError, OSError, TypeError, RuntimeError) as exc:
        logger.debug(
            "[SessionMetaCache] hgetall error code=%s: %s", code, exc,
        )
        return entry[0] if entry is not None else None

    if not raw:
        _cache.pop(code, None)
        return None

    decoded = {_decode(k): _decode(v) for k, v in raw.items()}
    if len(_cache) >= _CACHE_MAX_ENTRIES:
        for _ in range(_CACHE_EVICT_COUNT):
            if _cache:
                _cache.popitem(last=False)
    _cache[code] = (decoded, now)
    return decoded


def invalidate_session_meta(code: str) -> None:
    """Drop any cached entry for ``code`` (call after a write)."""
    if code:
        _cache.pop(code, None)


def clear_all_session_meta_cache() -> None:
    """Diagnostics helper; clears the full process-local cache."""
    _cache.clear()
