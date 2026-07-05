"""
Idle / zombie monitor for MindMate collab rooms.

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

from services.features.mindmate_collab.config import (
    MINDMATE_COLLAB_IDLE_GRACE_SECONDS,
    MINDMATE_COLLAB_IDLE_SILENCE_SECONDS,
    MINDMATE_COLLAB_MONITOR_CONCURRENCY,
    MINDMATE_COLLAB_MONITOR_INTERVAL_SECONDS,
    MINDMATE_COLLAB_ZOMBIE_GRACE_SECONDS,
)
from services.features.mindmate_collab.manager_access import get_mindmate_collab_manager
from services.features.mindmate_collab.redis_keys import (
    idle_scores_key,
    participants_key,
    room_idle_kick_lock_key,
    room_idle_warning_key,
)
from services.features.mindmate_collab.ws_broadcast import broadcast_to_all
from services.infrastructure.monitoring.ws_metrics import record_ws_idle_monitor_cycle
from services.online_collab.redis.online_collab_redis_locks import acquire_nx_lock, new_lock_token
from services.redis.redis_async_client import get_async_redis
from services.utils.error_types import BACKGROUND_INFRA_ERRORS, REDIS_ERRORS

logger = logging.getLogger(__name__)


class _IdleMonitorState:
    """Holds the background idle-monitor asyncio task."""

    task: Optional[asyncio.Task] = None


_idle_monitor_state = _IdleMonitorState()


async def _evaluate_code(code: str) -> None:
    mgr = get_mindmate_collab_manager()
    redis = get_async_redis()
    if not redis:
        return
    meta = await mgr.get_session_meta(code)
    if not meta:
        return
    session_id = meta.get("session_id") or ""
    if not session_id:
        return

    expires_raw = meta.get("expires_at")
    now = int(time.time())
    if expires_raw:
        try:
            if int(expires_raw) <= now:
                await mgr.stop_session(session_id, int(meta.get("owner_id") or 0), reason="expired")
                return
        except ValueError:
            pass

    try:
        participants = int(await redis.hlen(participants_key(code)) or 0)
    except (RedisError, OSError, RuntimeError, TypeError, ValueError):
        participants = 0

    last_raw = meta.get("last_activity") or "0"
    try:
        last_activity = int(last_raw)
    except ValueError:
        last_activity = now

    if participants == 0 and now - last_activity >= MINDMATE_COLLAB_ZOMBIE_GRACE_SECONDS:
        await mgr.stop_session(session_id, int(meta.get("owner_id") or 0), reason="zombie")
        return

    silence = now - last_activity
    if silence >= MINDMATE_COLLAB_IDLE_SILENCE_SECONDS + MINDMATE_COLLAB_IDLE_GRACE_SECONDS:
        lock = await acquire_nx_lock(redis, room_idle_kick_lock_key(code), 300, new_lock_token())
        if lock:
            await mgr.stop_session(session_id, int(meta.get("owner_id") or 0), reason="idle")
        return

    if silence >= MINDMATE_COLLAB_IDLE_SILENCE_SECONDS:
        warn_key = room_idle_warning_key(code)
        try:
            sent = await redis.set(warn_key, "1", nx=True, ex=MINDMATE_COLLAB_IDLE_GRACE_SECONDS)
        except REDIS_ERRORS:
            sent = False
        if sent:
            await broadcast_to_all(
                code,
                {
                    "type": "room_idle_warning",
                    "grace_seconds": MINDMATE_COLLAB_IDLE_GRACE_SECONDS,
                },
            )


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
                                    "[MindmateCollabIdle] evaluate failed code=%s: %s",
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
                logger.debug("[MindmateCollabIdle] scan error: %s", exc)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=MINDMATE_COLLAB_MONITOR_INTERVAL_SECONDS)
        except asyncio.TimeoutError:
            continue


def start_mindmate_collab_idle_monitor() -> asyncio.Task:
    """Start the background idle-room monitor task."""
    stop_event = asyncio.Event()
    _idle_monitor_state.task = asyncio.create_task(
        _monitor_loop(stop_event),
        name="mindmate-collab-idle-monitor",
    )
    return _idle_monitor_state.task
