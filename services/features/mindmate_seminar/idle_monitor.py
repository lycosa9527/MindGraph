"""
Idle-score monitor for MindMate seminar rooms.

Silence, an empty roster, duration presets, and room age do not end a room.
The leader ends the seminar. This loop only drops orphan idle scores.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

from redis.exceptions import RedisError

from services.features.mindmate_seminar.config import (
    MINDMATE_COLLAB_MONITOR_CONCURRENCY,
    MINDMATE_COLLAB_MONITOR_INTERVAL_SECONDS,
    MINDMATE_COLLAB_ZOMBIE_GRACE_SECONDS,
)
from services.features.mindmate_seminar.manager_access import get_mindmate_seminar_manager
from services.features.mindmate_seminar.redis_keys import (
    idle_scores_key,
    normalize_collab_code,
    session_meta_key,
)
from services.infrastructure.monitoring.ws_metrics import record_ws_idle_monitor_cycle
from services.redis.redis_async_client import get_async_redis
from services.utils.error_types import BACKGROUND_INFRA_ERRORS, REDIS_ERRORS

logger = logging.getLogger(__name__)


class _IdleMonitorState:
    """Holds the background idle-monitor asyncio task."""

    task: Optional[asyncio.Task] = None


_idle_monitor_state = _IdleMonitorState()


async def drop_orphan_mindmate_seminar_idle_score(code: str) -> None:
    """Remove an idle-monitor score when the live room hash is already gone."""
    redis = get_async_redis()
    if not redis:
        return
    norm = normalize_collab_code(code)
    meta_key = session_meta_key(norm)
    try:
        if await redis.exists(meta_key):
            if await redis.hexists(meta_key, "session_id"):
                return
            await redis.delete(meta_key)
        await redis.zrem(idle_scores_key(), norm)
    except REDIS_ERRORS:
        return


async def _evaluate_code(code: str) -> None:
    """Drop an idle score whose live Redis room is already gone."""
    mgr = get_mindmate_seminar_manager()
    redis = get_async_redis()
    if not redis:
        return
    meta = await mgr.get_session_meta(code)
    session_id = (meta.get("session_id") or "") if meta else ""
    if not session_id:
        await drop_orphan_mindmate_seminar_idle_score(code)


async def _monitor_loop(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        redis = get_async_redis()
        if redis:
            try:
                cutoff = time.time() - MINDMATE_COLLAB_ZOMBIE_GRACE_SECONDS
                stale = await redis.zrangebyscore(idle_scores_key(), "-inf", cutoff)
                stale_codes: list[str] = []
                for raw_code in stale or []:
                    code = raw_code.decode("utf-8") if isinstance(raw_code, bytes) else str(raw_code)
                    stale_codes.append(code)
                if stale_codes:
                    record_ws_idle_monitor_cycle()
                    sem = asyncio.Semaphore(MINDMATE_COLLAB_MONITOR_CONCURRENCY)

                    async def _evaluate_isolated(room_code: str) -> None:
                        async with sem:
                            try:
                                await _evaluate_code(room_code)
                            except (
                                RedisError,
                                OSError,
                                RuntimeError,
                                TypeError,
                                ValueError,
                                AttributeError,
                            ) as exc:
                                logger.warning(
                                    "[MindmateSeminarIdle] evaluate failed code=%s: %s",
                                    room_code,
                                    exc,
                                )

                    async with asyncio.TaskGroup() as tg:
                        for room_code in stale_codes:
                            tg.create_task(
                                _evaluate_isolated(room_code),
                                name=f"mindmate-idle-eval:{room_code}",
                            )
            except BACKGROUND_INFRA_ERRORS as exc:
                logger.debug("[MindmateSeminarIdle] scan error: %s", exc)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=MINDMATE_COLLAB_MONITOR_INTERVAL_SECONDS)
        except asyncio.TimeoutError:
            continue


def start_mindmate_seminar_idle_monitor() -> asyncio.Task:
    """Start the background idle-room monitor task."""
    stop_event = asyncio.Event()
    _idle_monitor_state.task = asyncio.create_task(
        _monitor_loop(stop_event),
        name="mindmate-seminar-idle-monitor",
    )
    return _idle_monitor_state.task
