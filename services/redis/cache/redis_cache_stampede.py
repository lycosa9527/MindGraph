"""
Cache stampede protection helper (G6 from db-tuning audit).
==========================================================

Prevents the "thundering herd" pattern that bites every cache-aside system:

    1. A hot cache key expires (or is evicted, or has not been warmed yet).
    2. ``N`` concurrent requests miss the cache simultaneously.
    3. All ``N`` requests hammer Postgres with the *same* query.
    4. Each one writes the same value back into Redis.

This module adds a lightweight per-key SETNX lock so that only one request
("the winner") executes the loader, while the others ("losers") briefly poll
for the lock to release and then re-read the cache.  If the winner finished
and populated the cache the losers see a hit; if the loader failed or the
wait expired they fall back to running the loader themselves so a single
stuck loader cannot cascade into a request timeout.

Design choices
--------------
* SETNX with a short TTL (default 10 s) so a crashed winner cannot wedge
  the key forever.
* Bounded poll loop (default 2 s, 50 ms interval) so the request budget
  is predictable.
* Disable-by-env (``CACHE_STAMPEDE_LOCK=false``) plus automatic bypass when
  Redis is unavailable so this can never be the reason a request fails.
* No global state; safe to import from any cache module.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2026 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import logging
import os
import secrets
import time
from typing import Awaitable, Callable, Optional, TypeVar

from services.redis.redis_async_client import get_async_redis
from services.redis.redis_async_ops import AsyncRedisOps
from services.redis.redis_client import is_redis_available

logger = logging.getLogger(__name__)

T = TypeVar("T")

_LOCK_KEY_PREFIX = "cache:loading:"
_DEFAULT_LOCK_TTL_S = 10
_DEFAULT_WAIT_TIMEOUT_S = 2.0
_DEFAULT_POLL_INTERVAL_S = 0.05


def _stampede_enabled() -> bool:
    """Single env switch so operators can disable this without redeploying.

    Defaults to ``true``.  Re-evaluated on every call so a config reload
    or feature toggle takes effect without restarting the process.
    """
    return os.getenv("CACHE_STAMPEDE_LOCK", "true").strip().lower() != "false"


async def with_stampede_lock(
    cache_key: str,
    loader: Callable[[], Awaitable[Optional[T]]],
    cache_reader: Optional[Callable[[], Awaitable[Optional[T]]]] = None,
    *,
    lock_ttl: int = _DEFAULT_LOCK_TTL_S,
    wait_timeout: float = _DEFAULT_WAIT_TIMEOUT_S,
    poll_interval: float = _DEFAULT_POLL_INTERVAL_S,
) -> Optional[T]:
    """Run ``loader`` once across concurrent callers for the same ``cache_key``.

    The first arrival acquires ``cache:loading:{cache_key}`` via SETNX with a
    short TTL and runs ``loader``.  Subsequent arrivals poll for the lock to
    release (capped at ``wait_timeout`` seconds, polling every
    ``poll_interval`` seconds), then call ``cache_reader`` to pick up the
    value the winner just wrote.  If ``cache_reader`` still returns ``None``
    (winner failed, was slow, or no reader was supplied), losers fall back
    to running ``loader`` themselves so request latency is bounded.

    Args:
        cache_key: Stable identifier for the value being loaded — used only
            to construct the lock key.  Pass the same string each time you
            ask for the same logical record.
        loader: Async function that performs the expensive load (typically a
            DB query) and is responsible for populating the cache itself.
        cache_reader: Optional async function the loser uses to re-read the
            cache after the winner finishes.  Should return ``None`` on
            miss.
        lock_ttl: Maximum seconds the SETNX lock can survive.  Set generous
            enough for the loader to finish; if the loader exceeds it the
            lock auto-expires and another worker will retry.
        wait_timeout: Maximum seconds losers will wait for the winner.
        poll_interval: Seconds between EXISTS polls.

    Returns:
        Whatever ``loader`` returns (or ``cache_reader`` returns on the
        loser path), or ``None`` on total failure.
    """
    if not _stampede_enabled() or not is_redis_available():
        return await loader()

    redis = get_async_redis()
    if redis is None:
        return await loader()

    lock_key = _LOCK_KEY_PREFIX + cache_key
    lock_id = secrets.token_hex(8)

    try:
        acquired = await redis.set(lock_key, lock_id, nx=True, ex=lock_ttl)
    except Exception as exc:  # pylint: disable=broad-except
        # Lock acquisition itself failed — skip protection and just load.
        logger.debug("[Stampede] SETNX failed for %s: %s", cache_key[:40], exc)
        return await loader()

    if acquired:
        try:
            return await loader()
        finally:
            try:
                await AsyncRedisOps.compare_and_delete(lock_key, lock_id)
            except Exception as exc:  # pylint: disable=broad-except
                logger.debug(
                    "[Stampede] lock release failed for %s: %s",
                    cache_key[:40],
                    exc,
                )

    # Loser path — bounded wait for the winner.
    deadline = time.monotonic() + max(0.0, wait_timeout)
    while time.monotonic() < deadline:
        await asyncio.sleep(poll_interval)
        try:
            still_locked = await redis.exists(lock_key)
        except Exception:  # pylint: disable=broad-except
            break
        if not still_locked:
            break

    if cache_reader is not None:
        try:
            value = await cache_reader()
            if value is not None:
                return value
        except Exception as exc:  # pylint: disable=broad-except
            logger.debug(
                "[Stampede] cache_reader failed for %s: %s",
                cache_key[:40],
                exc,
            )

    # Either no reader supplied, the winner failed, or the wait timed out.
    # Run the loader directly — better one duplicate query than a stuck
    # request.
    return await loader()
