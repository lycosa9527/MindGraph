"""Long-wait SETNX coalescer for organization generation-result cache misses.

Unlike ``with_stampede_lock`` (2s wait / 10s lock for Postgres), this helper
is sized for a 30–90s LLM call so 100–200 teachers searching the same topic
share one generation.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import logging
import secrets
import time
from collections.abc import Awaitable, Callable
from typing import Optional, TypeVar

from services.redis import keys as redis_keys
from services.redis.redis_async_client import get_async_redis
from services.redis.redis_async_ops import AsyncRedisOps
from services.redis.redis_client import is_redis_available
from services.utils.error_types import REDIS_ERRORS

logger = logging.getLogger(__name__)

T = TypeVar("T")


async def coalesce_generation(
    lock_key: str,
    loader: Callable[[], Awaitable[T]],
    cache_reader: Callable[[], Awaitable[Optional[T]]],
    *,
    on_acquired: Callable[[], Awaitable[None]] | None = None,
    on_waiting: Callable[[], Awaitable[None]] | None = None,
    cancel_event: asyncio.Event | None = None,
    lock_ttl: int | None = None,
    wait_timeout: float | None = None,
    poll_interval: float | None = None,
) -> T:
    """Run ``loader`` once across concurrent callers for ``lock_key``.

    The winner acquires the lock, optionally notifies ``on_acquired``, then
    runs ``loader`` (which must populate the cache). Losers emit
    ``on_waiting`` once, poll until the lock disappears or ``wait_timeout``
    elapses, then ``cache_reader``. If the reader still misses they fall
    back to ``loader``. A set ``cancel_event`` aborts waiters without
    running the loader.
    """
    resolved_lock_ttl = redis_keys.TTL_GEN_RESULT_LOCK if lock_ttl is None else lock_ttl
    resolved_wait = redis_keys.GEN_RESULT_WAIT_TIMEOUT if wait_timeout is None else wait_timeout
    resolved_poll = redis_keys.GEN_RESULT_POLL_INTERVAL if poll_interval is None else poll_interval

    if not is_redis_available():
        return await loader()

    redis = get_async_redis()
    if redis is None:
        return await loader()

    lock_id = secrets.token_hex(8)
    try:
        acquired = await redis.set(lock_key, lock_id, nx=True, ex=resolved_lock_ttl)
    except REDIS_ERRORS as exc:
        logger.debug("[GenResultCoalesce] SETNX failed for %s: %s", lock_key[:48], exc)
        return await loader()

    if acquired:
        if on_acquired is not None:
            await on_acquired()
        try:
            return await loader()
        finally:
            try:
                await AsyncRedisOps.compare_and_delete(lock_key, lock_id)
            except REDIS_ERRORS as exc:
                logger.debug(
                    "[GenResultCoalesce] lock release failed for %s: %s",
                    lock_key[:48],
                    exc,
                )

    if on_waiting is not None:
        await on_waiting()

    deadline = time.monotonic() + max(0.0, resolved_wait)
    poll = max(0.05, resolved_poll)
    while time.monotonic() < deadline:
        if cancel_event is not None and cancel_event.is_set():
            raise asyncio.CancelledError
        await asyncio.sleep(poll)
        if cancel_event is not None and cancel_event.is_set():
            raise asyncio.CancelledError
        try:
            still_locked = await redis.exists(lock_key)
        except REDIS_ERRORS:
            break
        if not still_locked:
            break

    if cancel_event is not None and cancel_event.is_set():
        raise asyncio.CancelledError

    try:
        value = await cache_reader()
    except REDIS_ERRORS as exc:
        logger.debug("[GenResultCoalesce] cache_reader failed for %s: %s", lock_key[:48], exc)
        value = None
    if value is not None:
        return value

    return await loader()
