"""Debounced + max-interval flush of Redis live spec to Postgres.

Multi-worker dedup: a Redis NX key (workshop:live_flush_pending:{code}) ensures
only one worker schedules the local asyncio debounce task for a given session.
The first worker to acquire the NX key becomes the designated flusher; all
others skip scheduling until the key expires (LIVE_FLUSH_DEBOUNCE_SEC).

Flush interval is kept short (<=10 s) to minimise the data-loss window if Redis
evicts the live_spec key under memory pressure.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Dict

from redis.exceptions import RedisError

from services.redis.redis_async_client import get_async_redis
from services.online_collab.spec.online_collab_live_spec_ops import flush_live_spec_to_db
from services.online_collab.redis.online_collab_redis_keys import (
    live_flush_pending_key,
    live_last_db_flush_key,
)

logger = logging.getLogger(__name__)

LIVE_FLUSH_DEBOUNCE_SEC = 8.0
LIVE_FLUSH_MAX_INTERVAL_SEC = 10.0

_pending: Dict[str, asyncio.Task] = {}  # type: ignore[type-arg]
_lock = asyncio.Lock()


async def cancel_all_pending_live_spec_db_flushes() -> None:
    """
    Cancel in-process debounced flush tasks (best-effort).

    Called during application shutdown so a follow-up full flush scan does not
    race with timers spawned by the same process.
    """
    async with _lock:
        pending_items = list(_pending.items())
        _pending.clear()
    for _, task in pending_items:
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


async def schedule_live_spec_db_flush(code: str, diagram_id: str) -> None:
    """
    After each live-spec mutation: flush immediately if max interval elapsed,
    else debounce (cancel prior timer, schedule new one).

    A Redis NX key prevents multiple Uvicorn workers from each running their
    own debounce task for the same session — only the first worker to acquire
    the key schedules the local asyncio task.
    """
    redis = get_async_redis()
    if not redis:
        return

    try:
        raw = await redis.get(live_last_db_flush_key(code))
    except (RedisError, OSError, RuntimeError, TypeError) as exc:
        logger.debug("[LiveSpec] flush last-ts read failed code=%s: %s", code, exc)
        raw = None
    last_ts = 0.0
    if raw is not None:
        try:
            last_ts = float(raw)
        except (TypeError, ValueError):
            last_ts = 0.0
    now = time.time()
    if now - last_ts >= LIVE_FLUSH_MAX_INTERVAL_SEC:
        await flush_live_spec_to_db(code, diagram_id)
        return

    pending_key = live_flush_pending_key(code)
    try:
        acquired = await redis.set(
            pending_key, "1", nx=True, ex=int(LIVE_FLUSH_DEBOUNCE_SEC) + 2
        )
    except (RedisError, OSError, RuntimeError, TypeError) as exc:
        logger.debug("[LiveSpec] flush NX key failed code=%s: %s", code, exc)
        acquired = True

    if not acquired:
        return

    async def _run() -> None:
        await asyncio.sleep(LIVE_FLUSH_DEBOUNCE_SEC)
        await flush_live_spec_to_db(code, diagram_id)

    async with _lock:
        old = _pending.pop(code, None)
        if old is not None and not old.done():
            old.cancel()
        try:
            task = asyncio.create_task(_run(), name=f"live_flush:{code}")
        except RuntimeError:
            await flush_live_spec_to_db(code, diagram_id)
            return
        _pending[code] = task

        def _cleanup(t: asyncio.Task) -> None:  # type: ignore[type-arg]
            if _pending.get(code) is t:
                _pending.pop(code, None)
            if t.cancelled():
                return
            err = t.exception()
            if err is not None:
                logger.debug("[LiveSpec] debounced flush task ended: %s", err)

        task.add_done_callback(_cleanup)
