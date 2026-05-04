"""
Idle monitoring for workshop / online-collaboration sessions.

Scans idle_scores periodically, evaluates zombie / expiry / silence, emits
warnings, and tears down sessions via the manager kick API.

Copyright 2024-2025 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any, Awaitable, Protocol, cast

from redis.exceptions import RedisError

from services.redis.redis_async_client import get_async_redis
from services.infrastructure.monitoring.ws_metrics import record_ws_idle_monitor_cycle

from services.online_collab.redis.online_collab_redis_keys import (
    idle_scores_key,
    participants_key,
    room_idle_kick_lock_key,
    room_idle_warning_sent_key,
    session_meta_key,
)

logger = logging.getLogger(__name__)


def _int_env(var: str, default: int) -> int:
    raw = os.getenv(var, "").strip()
    try:
        return max(1, int(raw)) if raw else default
    except ValueError:
        return default


ZOMBIE_GRACE_SEC = _int_env("WORKSHOP_ZOMBIE_GRACE_SECONDS", 1800)
IDLE_SILENCE_SEC = _int_env("WORKSHOP_IDLE_SILENCE_SECONDS", 1800)
IDLE_GRACE_SEC = _int_env("WORKSHOP_IDLE_GRACE_SECONDS", 120)
MONITOR_INTERVAL = _int_env("WORKSHOP_MONITOR_INTERVAL_SECONDS", 15)
MONITOR_CONCURRENCY = _int_env("WORKSHOP_MONITOR_CONCURRENCY", 20)


def _decode_kv(val: Any) -> str:
    if isinstance(val, (bytes, bytearray)):
        return val.decode("utf-8", errors="replace")
    if isinstance(val, memoryview):
        return bytes(val).decode("utf-8", errors="replace")
    return str(val) if val is not None else ""


class _IdleKickTarget(Protocol):
    """Manager hook: stop a session after idle/expiry/zombie teardown."""

    async def stop_online_collab_for_room_idle(
        self,
        diagram_id: str,
        expected_code: str,
    ) -> bool: ...


async def broadcast_idle_warning(code: str, deadline_unix: int) -> None:
    """Send room_idle_warning to all participants once (NX-guarded)."""
    from routers.api.workshop_ws_broadcast import broadcast_to_all

    redis = get_async_redis()
    if not redis:
        return
    warn_key = room_idle_warning_sent_key(code)
    try:
        nx_set = await redis.set(warn_key, "1", nx=True, ex=IDLE_GRACE_SEC + 120)
    except (RedisError, OSError, TypeError, RuntimeError):
        return
    if nx_set:
        grace_rem = max(1, deadline_unix - int(time.time()))
        await broadcast_to_all(
            code,
            {
                "type": "room_idle_warning",
                "idle_deadline_unix": deadline_unix,
                "grace_seconds_remaining": grace_rem,
            },
        )
        logger.info(
            "[OnlineCollabMgr] idle_warning_sent code=%s deadline=%s grace_rem=%s",
            code,
            deadline_unix,
            grace_rem,
        )


async def destroy_and_stop_db_for_idle(
    manager: _IdleKickTarget,
    code: str,
    diagram_id: str,
    reason: str,
) -> None:
    """
    Broadcast shutdown, then stop the session in DB + Redis.

    Protected by a Redis NX lock so only one worker executes the destroy when
    multiple workers run the idle monitor concurrently.

    Delegates to stop_online_collab_for_room_idle (flush live spec, purge keys).
    """
    redis = get_async_redis()
    if not redis:
        logger.warning(
            "[OnlineCollabMgr] _destroy_and_stop_db: Redis unavailable, "
            "skipping to prevent multi-worker duplicate destroy code=%s reason=%s",
            code,
            reason,
        )
        return

    lock_key = room_idle_kick_lock_key(code)
    try:
        acquired = await redis.set(lock_key, "1", nx=True, ex=300)
    except (RedisError, OSError, TypeError, RuntimeError) as exc:
        logger.warning(
            "[OnlineCollabMgr] _destroy_and_stop_db: NX lock failed code=%s: %s",
            code,
            exc,
        )
        acquired = None
    if not acquired:
        logger.debug(
            "[OnlineCollabMgr] destroy_and_stop_db: skipped "
            "(another worker holds destroy lock) code=%s reason=%s",
            code,
            reason,
        )
        return

    logger.info(
        "[OnlineCollabMgr] session_destroying code=%s reason=%s diagram_id=%s",
        code,
        reason,
        diagram_id,
    )

    from routers.api.workshop_ws_broadcast import (
        broadcast_workshop_room_idle_shutdown,
    )

    await broadcast_workshop_room_idle_shutdown(code)
    await asyncio.sleep(0.08)

    stopped = await manager.stop_online_collab_for_room_idle(
        diagram_id, code.upper()
    )
    if stopped:
        logger.info(
            "[OnlineCollabMgr] session_destroyed code=%s reason=%s diagram_id=%s",
            code,
            reason,
            diagram_id,
        )
        return

    logger.warning(
        "[OnlineCollabMgr] destroy_and_stop_db: stop returned False "
        "code=%s reason=%s diagram_id=%s — clearing idle_scores entry",
        code,
        reason,
        diagram_id,
    )
    try:
        await redis.zrem(idle_scores_key(), code)
    except (RedisError, OSError, TypeError, RuntimeError):
        pass


async def evaluate_stale_code(manager: _IdleKickTarget, code: str, now: int) -> None:
    """Evaluate a single code that appeared in the stale ZSET window."""
    redis = get_async_redis()
    if not redis:
        return

    try:
        results = await asyncio.gather(
            cast(Awaitable[Any], redis.hgetall(session_meta_key(code))),
            cast(Awaitable[Any], redis.hlen(participants_key(code))),
            return_exceptions=True,
        )
    except (RedisError, OSError, TypeError, RuntimeError) as exc:
        logger.debug(
            "[OnlineCollabMgr] _evaluate_stale_code: gather error code=%s: %s",
            code,
            exc,
        )
        return

    meta_raw, count = results
    if isinstance(meta_raw, BaseException) or isinstance(count, BaseException):
        return

    if not isinstance(meta_raw, dict) or not meta_raw:
        try:
            await redis.zrem(idle_scores_key(), code)
        except (RedisError, OSError, TypeError, RuntimeError):
            pass
        return

    if not isinstance(count, int):
        return

    meta = {_decode_kv(k): _decode_kv(v) for k, v in meta_raw.items()}
    diagram_id = meta.get("diagram_id", "")

    if not diagram_id:
        logger.warning(
            "[OnlineCollabMgr] orphan_session_meta code=%s "
            "(missing diagram_id) — removing from idle_scores",
            code,
        )
        try:
            await redis.zrem(idle_scores_key(), code)
        except (RedisError, OSError, TypeError, RuntimeError):
            pass
        return

    expires_at_str = meta.get("expires_at", "")
    if expires_at_str:
        try:
            if now > int(expires_at_str):
                await destroy_and_stop_db_for_idle(
                    manager, code, diagram_id, "expired"
                )
                return
        except (TypeError, ValueError):
            pass

    if count == 0:
        await destroy_and_stop_db_for_idle(manager, code, diagram_id, "zombie")
        return

    last_activity_str = meta.get("last_activity", "")
    if not last_activity_str:
        return
    try:
        last_ts = int(last_activity_str)
    except (TypeError, ValueError):
        return

    elapsed = now - last_ts
    deadline = last_ts + IDLE_SILENCE_SEC + IDLE_GRACE_SEC

    if elapsed > IDLE_SILENCE_SEC + IDLE_GRACE_SEC:
        await destroy_and_stop_db_for_idle(manager, code, diagram_id, "idle")
    elif elapsed > IDLE_SILENCE_SEC:
        await broadcast_idle_warning(code, deadline)


async def idle_monitor_loop(manager: _IdleKickTarget) -> None:
    """
    Single long-running loop: scans idle_scores ZSET, evaluates stale sessions.

    Replaces N per-WebSocket asyncio tasks with one shared task.
    Exponential back-off on repeated Redis failures (max 5 extra sleeps).
    """
    logger.info(
        "[OnlineCollabMgr] Idle monitor started interval=%ss zombie_grace=%ss "
        "idle_silence=%ss idle_grace=%ss",
        MONITOR_INTERVAL,
        ZOMBIE_GRACE_SEC,
        IDLE_SILENCE_SEC,
        IDLE_GRACE_SEC,
    )
    backoff = 0
    while True:
        try:
            await asyncio.sleep(MONITOR_INTERVAL)

            redis = get_async_redis()
            if not redis:
                logger.warning(
                    "[OnlineCollabMgr] idle monitor: redis_unavailable_fallback"
                )
                backoff = min(backoff + 1, 5)
                await asyncio.sleep(MONITOR_INTERVAL * backoff)
                continue
            backoff = 0

            now = int(time.time())
            stale_cutoff = float(now - ZOMBIE_GRACE_SEC)

            try:
                stale_raw = await redis.zrangebyscore(
                    idle_scores_key(), 0, stale_cutoff
                )
            except (RedisError, OSError, TypeError, RuntimeError) as exc:
                logger.warning(
                    "[OnlineCollabMgr] idle monitor: zrangebyscore error: %s", exc
                )
                continue

            if not stale_raw:
                continue

            stale_codes = [
                c.decode("utf-8") if isinstance(c, bytes) else c for c in stale_raw
            ]
            logger.debug(
                "[OnlineCollabMgr] monitor_cycle_start n_stale=%s", len(stale_codes)
            )
            record_ws_idle_monitor_cycle()

            sem = asyncio.Semaphore(MONITOR_CONCURRENCY)

            async def _evaluate_isolated(c: str) -> None:
                async with sem:
                    try:
                        await evaluate_stale_code(manager, c, now)
                    except Exception as exc:
                        logger.warning(
                            "[OnlineCollabMgr] _evaluate_stale_code failed "
                            "code=%s: %s",
                            c,
                            exc,
                        )

            async with asyncio.TaskGroup() as tg:
                for cod in stale_codes:
                    tg.create_task(
                        _evaluate_isolated(cod),
                        name=f"idle_eval:{cod}",
                    )

        except asyncio.CancelledError:
            logger.info(
                "[OnlineCollabMgr] Idle monitor task cancelled, shutting down"
            )
            raise
        except Exception as exc:
            logger.error(
                "[OnlineCollabMgr] Idle monitor unexpected error: %s",
                exc,
                exc_info=True,
            )


__all__ = [
    "IDLE_GRACE_SEC",
    "IDLE_SILENCE_SEC",
    "MONITOR_CONCURRENCY",
    "MONITOR_INTERVAL",
    "ZOMBIE_GRACE_SEC",
    "broadcast_idle_warning",
    "destroy_and_stop_db_for_idle",
    "evaluate_stale_code",
    "idle_monitor_loop",
]
