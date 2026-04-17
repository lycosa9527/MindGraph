"""Debounced + max-interval flush of Redis live spec to Postgres."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Dict

from services.redis.redis_async_client import get_async_redis
from services.workshop.workshop_live_spec_ops import flush_live_spec_to_db
from services.workshop.workshop_redis_keys import live_last_db_flush_key

logger = logging.getLogger(__name__)

LIVE_FLUSH_DEBOUNCE_SEC = 45.0
LIVE_FLUSH_MAX_INTERVAL_SEC = 60.0

_pending: Dict[str, asyncio.Task] = {}
_lock = asyncio.Lock()


async def schedule_live_spec_db_flush(code: str, diagram_id: str) -> None:
    """
    After each live-spec mutation: flush immediately if max interval elapsed,
    else debounce (cancel prior timer, schedule new one).
    """
    redis = get_async_redis()
    if not redis:
        return

    raw = await redis.get(live_last_db_flush_key(code))
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

    async def _run() -> None:
        await asyncio.sleep(LIVE_FLUSH_DEBOUNCE_SEC)
        await flush_live_spec_to_db(code, diagram_id)

    async with _lock:
        old = _pending.pop(code, None)
        if old is not None and not old.done():
            old.cancel()
        try:
            task = asyncio.create_task(_run())
        except RuntimeError:
            # no running loop (should not happen in WS handler)
            await flush_live_spec_to_db(code, diagram_id)
            return
        _pending[code] = task

        def _cleanup(t: asyncio.Task) -> None:
            if _pending.get(code) is t:
                _pending.pop(code, None)
            if t.cancelled():
                return
            err = t.exception()
            if err is not None:
                logger.debug("[LiveSpec] debounced flush task ended: %s", err)

        task.add_done_callback(_cleanup)
