"""
Workshop Session Manager: centralized lifecycle controller.

Idle expiry / zombie / silence handling runs in ``online_collab_idle_monitor``.
This module owns orchestration hooks and Redis session layout:

Redis layout owned here:
  workshop:sessionmeta:{code}     HASH  ??diagram_id, owner_id, org_id, visibility,
                                          title, owner_name, expires_at, last_activity
  workshop:registry:org:{org_id}  SET   ??active org-scope codes
  workshop:registry:network       SET   ??active network-scope codes
  workshop:idle_scores            ZSET  ??code ??last_activity unix ts

Copyright 2024-2025 ???????????? (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from datetime import datetime
from typing import Any, Awaitable, Callable, Coroutine, Dict, List, Optional, Tuple, cast

from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from sqlalchemy.ext.asyncio import AsyncSession

from config.database import AsyncSessionLocal
from models.domain.diagrams import Diagram

from services.online_collab.core.online_collab_code import (
    ONLINE_COLLAB_MAX_PARTICIPANTS,
    ONLINE_COLLAB_SESSION_TTL,
    _allocate_unique_online_collab_code,
    _online_collab_start_session_redis_value,
    _online_collab_start_validation_error,
)
from services.online_collab.core.online_collab_status import (
    get_online_collab_status_for_viewer,
    list_org_online_collab_sessions_for_user,
)
from services.online_collab.core.online_collab_lifecycle import (
    cleanup_expired_online_collabs_impl,
)
from services.online_collab.lifecycle.online_collab_expiry import (
    DURATION_TODAY,
    is_online_collab_expired,
    redis_ttl_seconds_for_expires_at,
)
from services.online_collab.lifecycle.online_collab_join_helpers import (
    restore_online_collab_redis_from_db_row,
)
from services.online_collab.lifecycle.online_collab_session_fields import (
    backfill_online_collab_expiry_if_needed,
)
from services.online_collab.lifecycle.online_collab_visibility_helpers import (
    ONLINE_COLLAB_VISIBILITY_NETWORK,
    ONLINE_COLLAB_VISIBILITY_ORGANIZATION,
    clear_expired_online_collab_session,
    diagram_online_collab_visibility,
    user_may_join_diagram_online_collab,
)
from services.online_collab.participant.online_collab_participant_ops import (
    ONLINE_COLLAB_PARTICIPANTS_TTL,
    get_participants_for_code,
    participant_count_for_code,
    refresh_participant_ttl_for_code,
    remove_participant_from_online_collab,
)

from services.redis.redis_async_client import get_async_redis
from services.online_collab.lifecycle.session_meta_cache import (
    get_session_meta_cached,
    invalidate_session_meta,
)
from services.online_collab.redis.online_collab_redis_keys import (
    code_to_diagram_key,
    idle_scores_key,
    participants_key,
    purge_online_collab_redis_keys,
    registry_global_org_key,
    registry_network_key,
    registry_org_key,
    session_meta_key,
)
from services.online_collab.redis.online_collab_redis_scripts import (
    JOIN_CAP_SCRIPT_NAME,
    evalsha_with_reload,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Redis durability helper
# ---------------------------------------------------------------------------

def _redis_wait_enabled() -> bool:
    return os.getenv("COLLAB_REDIS_WAIT_DURABILITY", "0") not in ("0", "false", "False", "")


async def _redis_wait(redis: Any) -> None:
    """
    Issue ``WAIT 1 200`` (wait for ≥1 replica ACK within 200 ms) after a
    critical write pipeline when ``COLLAB_REDIS_WAIT_DURABILITY=1``.

    Non-fatal: errors and timeouts are silently swallowed so the hot path
    is never blocked on replica health.  Only active when the env flag is
    explicitly enabled — default is off to avoid latency on single-node
    setups.
    """
    if not _redis_wait_enabled():
        return
    try:
        await redis.wait(1, 200)
    except Exception:  # pylint: disable=broad-except
        pass


# ---------------------------------------------------------------------------
# Decode helper
# ---------------------------------------------------------------------------

def _s(val: Any) -> str:
    """Decode bytes / memoryview to str; return '' for None."""
    if isinstance(val, (bytes, bytearray)):
        return val.decode("utf-8", errors="replace")
    if isinstance(val, memoryview):
        return bytes(val).decode("utf-8", errors="replace")
    return str(val) if val is not None else ""


# ---------------------------------------------------------------------------
# OnlineCollabManager
# ---------------------------------------------------------------------------

class OnlineCollabManager:
    """
    Singleton lifecycle controller for workshop sessions.

    All public coroutines are safe to call concurrently.  A per-code
    asyncio.Lock (_destroy_locks) prevents double-destroy races; _destroy_locks
    itself is guarded by _destroy_locks_mutex.
    """

    def __init__(self) -> None:
        self._destroy_locks: Dict[str, asyncio.Lock] = {}
        self._destroy_locks_mutex = asyncio.Lock()
        self._idle_monitor_task: Optional[asyncio.Task] = None

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    async def create_session(
        self,
        *,
        code: str,
        diagram_id: str,
        owner_id: int,
        org_id: Optional[int],
        visibility: str,
        expires_at_unix: int,
        ttl_sec: int,
        title: str = "",
        owner_name: str = "",
    ) -> None:
        """
        Register a new session in Redis.

        Writes:
          HSET  workshop:sessionmeta:{code}  ??full session metadata
          SADD  workshop:registry:org:{org_id} or workshop:registry:network
          ZADD  workshop:idle_scores  code ??now
        """
        redis = get_async_redis()
        if not redis:
            logger.warning(
                "[OnlineCollabMgr] create_session skipped ??Redis unavailable code=%s", code
            )
            return
        now = int(time.time())
        meta = {
            "diagram_id": diagram_id,
            "owner_id": str(owner_id),
            "org_id": str(org_id) if org_id is not None else "",
            "visibility": visibility,
            "expires_at": str(expires_at_unix),
            "last_activity": str(now),
            "started_at": str(now),
            "title": title or "",
            "owner_name": owner_name or "",
        }
        try:
            async with redis.pipeline(transaction=False) as pipe:
                pipe.hset(session_meta_key(code), mapping=meta)
                pipe.expire(session_meta_key(code), ttl_sec)
                if org_id is not None:
                    pipe.sadd(registry_org_key(org_id), code)
                elif visibility == "organization":
                    pipe.sadd(registry_global_org_key(), code)
                if visibility == "network":
                    pipe.sadd(registry_network_key(), code)
                pipe.zadd(idle_scores_key(), {code: float(now)})
                await pipe.execute()
            await _redis_wait(redis)
            invalidate_session_meta(code)
            logger.info(
                "[OnlineCollabMgr] session_created code=%s diagram_id=%s owner_id=%s "
                "org_id=%s visibility=%s expires_at=%s",
                code,
                diagram_id,
                owner_id,
                org_id,
                visibility,
                expires_at_unix,
            )
        except (RedisError, OSError, TypeError, RuntimeError) as exc:
            logger.warning(
                "[OnlineCollabMgr] create_session Redis error code=%s: %s", code, exc
            )

    async def destroy_session(
        self,
        code: str,
        *,
        reason: str = "explicit",
        diagram_id: str = "",
    ) -> bool:
        """
        Purge all Redis keys for a session (registry + idle_scores + all keys).

        Uses a per-code asyncio.Lock to prevent double-destroy races.
        Returns True if this call performed the destroy, False if already locked.
        DB clearing is the caller's responsibility (either stop_online_collab or
        stop_online_collab_for_room_idle performs it).
        """
        async with self._destroy_locks_mutex:
            if code not in self._destroy_locks:
                self._destroy_locks[code] = asyncio.Lock()
            lock = self._destroy_locks[code]

        if lock.locked():
            logger.warning(
                "[OnlineCollabMgr] destroy_session: double-destroy attempt code=%s reason=%s",
                code,
                reason,
            )
            return False

        async with lock:
            try:
                return await self._destroy_session_inner(code, reason=reason, diagram_id=diagram_id)
            finally:
                async with self._destroy_locks_mutex:
                    self._destroy_locks.pop(code, None)

    async def _destroy_session_inner(
        self,
        code: str,
        *,
        reason: str,
        diagram_id: str,
    ) -> bool:
        """Execute the purge body — always called while holding the per-code lock."""
        redis = get_async_redis()
        if not redis:
            logger.warning(
                "[OnlineCollabMgr] destroy_session: Redis unavailable code=%s", code
            )
            return False

        meta: dict = {}
        try:
            meta = (
                await cast(
                    Awaitable[Any],
                    redis.hgetall(session_meta_key(code)),
                )
                or {}
            )
        except (RedisError, OSError, TypeError, RuntimeError):
            pass

        if not meta and reason not in ("explicit", "expired"):
            logger.warning(
                "[OnlineCollabMgr] destroy_session: no meta found code=%s reason=%s "
                "(may already be destroyed)",
                code,
                reason,
            )

        try:
            await purge_online_collab_redis_keys(redis, code)
        except (RedisError, OSError, TypeError, RuntimeError) as exc:
            logger.warning(
                "[OnlineCollabMgr] destroy_session: purge error code=%s reason=%s: %s",
                code,
                reason,
                exc,
            )
            return False

        await _redis_wait(redis)
        invalidate_session_meta(code)

        resolved_diagram_id = diagram_id or _s(
            meta.get(b"diagram_id") or meta.get("diagram_id")
        )
        logger.info(
            "[OnlineCollabMgr] session_destroyed code=%s reason=%s diagram_id=%s",
            code,
            reason,
            resolved_diagram_id,
        )
        return True

    # ------------------------------------------------------------------
    # Participant tracking
    # ------------------------------------------------------------------

    async def on_join(self, code: str, user_id: int) -> None:
        """Called when a user connects via WebSocket. Refreshes idle score."""
        await self.touch_activity(code)
        logger.info(
            "[OnlineCollabMgr] participant_joined code=%s user_id=%s", code, user_id
        )

    async def owner_name_for_code(self, code: str) -> Optional[str]:
        """
        Short-circuit owner-username lookup via the cached session_meta HASH.

        Uses the process-local :func:`get_session_meta_cached` to avoid a
        per-call HGET round-trip on the hot invite-list path. Returns
        ``None`` when no live session exists for ``code``.
        """
        if not code:
            return None
        meta = await get_session_meta_cached(code)
        if not meta:
            return None
        name = (meta.get("owner_name") or "").strip()
        return name or None

    async def on_leave(self, code: str, user_id: int) -> None:
        """
        Called when a user disconnects from WebSocket.

        Participant removal and touch_leave are handled by
        remove_participant_from_online_collab (workshop_participant_ops). This method
        only logs the event with the post-removal count.
        """
        redis = get_async_redis()
        count_after: Optional[int] = None
        if redis:
            try:
                count_after = await cast(
                    Awaitable[Any],
                    redis.hlen(participants_key(code)),
                )
            except (RedisError, OSError, TypeError, RuntimeError):
                pass
        logger.info(
            "[OnlineCollabMgr] participant_left code=%s user_id=%s count_after=%s",
            code,
            user_id,
            count_after,
        )

    async def touch_leave(self, code: str) -> None:
        """
        Update idle_scores after a participant departs.

        Keeps last_activity current so the monitor can detect zombie sessions
        (zero participants) after the configured zombie grace window.
        """
        await self.touch_activity(code)

    async def touch_activity(self, code: str) -> None:
        """
        Record diagram collaborative activity for idle tracking.

        Pipeline:
          - HSET session_meta last_activity=now
          - ZADD idle_scores{code: now}
          - EXPIRE session_meta <SAFETY_TTL> GT  (Redis 7.0+; no-op on older)

        ``EXPIRE ... GT`` only applies when the new TTL would be *greater*
        than the current TTL ??this keeps session_meta alive during long
        active sessions if someone has previously shortened the TTL (e.g.
        during an idle-eviction race) while never overriding the
        session-level expires_at. On Redis <7.0 the GT flag is unrecognised
        and the command raises, which we swallow.
        """
        redis = get_async_redis()
        if not redis:
            return
        now = int(time.time())
        safety_ttl_sec = 3600
        try:
            async with redis.pipeline(transaction=False) as pipe:
                pipe.hset(session_meta_key(code), "last_activity", str(now))
                pipe.zadd(idle_scores_key(), {code: float(now)})
                await pipe.execute()
            try:
                await redis.execute_command(
                    "EXPIRE", session_meta_key(code), safety_ttl_sec, "GT",
                )
            except RedisError as exp_exc:
                logger.debug(
                    "[OnlineCollabMgr] touch_activity EXPIRE GT skipped code=%s: %s",
                    code, exp_exc,
                )
            invalidate_session_meta(code)
            logger.debug(
                "[OnlineCollabMgr] activity_touched code=%s ts=%s", code, now
            )
        except (RedisError, OSError, TypeError, RuntimeError) as exc:
            logger.debug(
                "[OnlineCollabMgr] touch_activity Redis error code=%s: %s", code, exc
            )

    def _redis_ttl_seconds_for_diagram(self, diagram: Diagram) -> int:
        if diagram.workshop_expires_at:
            return redis_ttl_seconds_for_expires_at(diagram.workshop_expires_at)
        return ONLINE_COLLAB_SESSION_TTL

    async def _finalize_join_after_load(
        self,
        db: AsyncSession,
        redis: Any,
        diagram: Diagram,
        diagram_id: str,
        code: str,
        user_id: int,
    ) -> Optional[Dict[str, Any]]:
        """Authorize join, add participant keys, return workshop info or None."""
        await backfill_online_collab_expiry_if_needed(diagram, db)
        if diagram.workshop_expires_at and is_online_collab_expired(
            diagram.workshop_expires_at
        ):
            if redis:
                await clear_expired_online_collab_session(diagram, db, redis)
            return None

        vis = diagram_online_collab_visibility(diagram)
        may_join = (
            vis == ONLINE_COLLAB_VISIBILITY_NETWORK
            or await user_may_join_diagram_online_collab(db, diagram, user_id)
        )
        if not may_join:
            logger.warning(
                "[OnlineCollabMgr] Join denied user=%s diagram=%s",
                user_id,
                diagram_id,
            )
            return None

        if not redis:
            logger.error("[OnlineCollabMgr] Redis client not available")
            return None

        p_key = participants_key(code)
        member_key = str(user_id)
        join_ts = str(int(time.time()))
        try:
            result = await evalsha_with_reload(
                redis,
                JOIN_CAP_SCRIPT_NAME,
                1,
                p_key,
                member_key,
                str(ONLINE_COLLAB_MAX_PARTICIPANTS),
                str(ONLINE_COLLAB_PARTICIPANTS_TTL),
                join_ts,
            )
        except (RedisError, TypeError, AttributeError, RuntimeError, OSError) as exc:
            logger.warning("[OnlineCollabMgr] Participant cap check failed: %s", exc)
            return None

        if result == -1:
            logger.warning(
                "[OnlineCollabMgr] Room full workshop=%s max=%s",
                code,
                ONLINE_COLLAB_MAX_PARTICIPANTS,
            )
            return None

        logger.info(
            "[OnlineCollabMgr] User %s joined workshop %s (diagram %s)",
            user_id,
            code,
            diagram_id,
        )

        return {
            "code": code,
            "diagram_id": diagram_id,
            "diagram_type": diagram.diagram_type,
            "title": diagram.title,
            "owner_id": diagram.user_id,
        }

    async def start_online_collab(
        self,
        diagram_id: str,
        user_id: int,
        visibility: str = ONLINE_COLLAB_VISIBILITY_ORGANIZATION,
        duration: str = DURATION_TODAY,
        target_org_id: Optional[int] = None,
    ) -> Tuple[Optional[str], Optional[str], Optional[datetime], int]:
        """Start collaboration session for ``diagram_id``."""
        from services.online_collab.core.online_collab_lifecycle import (
            start_online_collab_impl,
        )

        return await start_online_collab_impl(
            allocate_unique_code=_allocate_unique_online_collab_code,
            validation_error=_online_collab_start_validation_error,
            session_redis_value=_online_collab_start_session_redis_value,
            diagram_id=diagram_id,
            user_id=user_id,
            visibility=visibility,
            duration=duration,
            workshop_session_ttl=ONLINE_COLLAB_SESSION_TTL,
            target_org_id=target_org_id,
        )

    async def stop_online_collab(self, diagram_id: str, user_id: int) -> bool:
        """Owner-initiated collaboration stop."""
        from services.online_collab.core.online_collab_lifecycle import (
            stop_online_collab_impl,
        )

        return await stop_online_collab_impl(diagram_id, user_id)

    async def stop_online_collab_for_room_idle(
        self,
        diagram_id: str,
        expected_code: str,
    ) -> bool:
        """Idle-timer initiated stop."""
        from services.online_collab.core.online_collab_lifecycle import (
            stop_online_collab_for_room_idle_impl,
        )

        return await stop_online_collab_for_room_idle_impl(
            diagram_id, expected_code,
        )

    async def get_active_online_collab_code_for_diagram(
        self,
        diagram_id: str,
    ) -> Optional[str]:
        """Return active non-expired workshop code for diagram, else None."""
        async with AsyncSessionLocal() as db:
            try:
                result = await db.execute(
                    select(
                        Diagram.workshop_code,
                        Diagram.workshop_expires_at,
                    ).filter(
                        Diagram.id == diagram_id,
                        ~Diagram.is_deleted,
                    ),
                )
                row = result.first()
                if row is None:
                    return None
                active_code, active_expires = row
                if not active_code:
                    return None
                if active_expires and is_online_collab_expired(active_expires):
                    return None
                return active_code
            except SQLAlchemyError as exc:
                logger.debug(
                    "[OnlineCollabMgr] get_active_online_collab_code_for_diagram error "
                    "diagram_id=%s: %s",
                    diagram_id,
                    exc,
                )
                return None

    async def join_online_collab(
        self,
        code: str,
        user_id: int,
    ) -> Optional[Dict[str, Any]]:
        """Join collaboration by shared code."""
        async with AsyncSessionLocal() as db:
            try:
                code = code.strip()

                redis = get_async_redis()
                diagram_id = None
                if redis:
                    diagram_id_raw = await redis.get(code_to_diagram_key(code))
                    if diagram_id_raw:
                        diagram_id = (
                            diagram_id_raw
                            if isinstance(diagram_id_raw, str)
                            else diagram_id_raw.decode("utf-8")
                        )

                if not diagram_id:
                    result = await db.execute(
                        select(Diagram).filter(
                            Diagram.workshop_code == code,
                            ~Diagram.is_deleted,
                        ),
                    )
                    diagram = result.scalars().first()
                    if diagram:
                        diagram_id = diagram.id
                        if redis:
                            await backfill_online_collab_expiry_if_needed(
                                diagram, db,
                            )
                            ttl = self._redis_ttl_seconds_for_diagram(diagram)
                            await restore_online_collab_redis_from_db_row(
                                redis,
                                code,
                                diagram_id,
                                diagram,
                                ttl,
                            )

                if not diagram_id:
                    logger.warning(
                        "[OnlineCollabMgr] Invalid workshop code: %s",
                        code,
                    )
                    return None

                result = await db.execute(
                    select(Diagram).filter(
                        Diagram.id == diagram_id,
                        ~Diagram.is_deleted,
                    ),
                )
                diagram = result.scalars().first()
                if not diagram:
                    return None

                return await self._finalize_join_after_load(
                    db,
                    redis,
                    diagram,
                    diagram_id,
                    code,
                    user_id,
                )

            except (SQLAlchemyError, OSError) as exc:
                logger.error(
                    "[OnlineCollabMgr] Error joining workshop: %s",
                    exc,
                    exc_info=True,
                )
                return None

    async def join_online_collab_by_diagram(
        self,
        diagram_id: str,
        user_id: int,
    ) -> Optional[Dict[str, Any]]:
        """Join organization-scoped session by diagram id."""
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Diagram).filter(
                    Diagram.id == diagram_id,
                    ~Diagram.is_deleted,
                ),
            )
            diagram = result.scalars().first()
            if not diagram or not diagram.workshop_code:
                return None
            if (
                diagram_online_collab_visibility(diagram)
                != ONLINE_COLLAB_VISIBILITY_ORGANIZATION
            ):
                return None
            if not await user_may_join_diagram_online_collab(
                db, diagram, user_id,
            ):
                logger.warning(
                    "[OnlineCollabMgr] Org join denied user=%s diagram=%s",
                    user_id,
                    diagram_id,
                )
                return None
            org_code = diagram.workshop_code
        return await self.join_online_collab(org_code, user_id)

    async def get_participants(self, code: str) -> List[int]:
        """Return participant ids for ``code``."""
        return await get_participants_for_code(code)

    async def refresh_participant_ttl(self, code: str, user_id: int) -> None:
        """Extend participant TTL on activity."""
        await refresh_participant_ttl_for_code(code, user_id)

    async def remove_participant(self, code: str, user_id: int) -> None:
        """Leave room and trigger live flush wiring."""
        await remove_participant_from_online_collab(code, user_id)

    async def list_org_online_collab_sessions(
        self,
        user_id: int,
    ) -> List[Dict[str, Any]]:
        """List org-scope active sessions."""
        return await list_org_online_collab_sessions_for_user(user_id)

    async def get_online_collab_status(
        self,
        diagram_id: str,
        viewer_user_id: int,
    ) -> Tuple[Optional[Dict[str, Any]], str]:
        """Status payload plus error tag for viewers."""
        return await get_online_collab_status_for_viewer(
            diagram_id, viewer_user_id,
        )

    async def _participant_count_for_code(self, code: str) -> int:
        """Internal participant count probe for status/helpers."""
        return await participant_count_for_code(code)

    async def cleanup_expired_online_collabs(self) -> int:
        """Clear expired collaborations (scheduler entry)."""
        return await cleanup_expired_online_collabs_impl()

    async def list_org_sessions(
        self,
        org_id: int,
        db_fallback_fn: Optional[Callable[[], Coroutine[Any, Any, List[Dict[str, Any]]]]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Return live sessions for org_id (Redis-first, single-pipeline).

        Delegates to :func:`online_collab_org_listing.list_org_sessions_redis`.
        Falls back to db_fallback_fn when Redis is unavailable or registry is empty.
        """
        from services.online_collab.core.online_collab_org_listing import (  # pylint: disable=import-outside-toplevel
            list_org_sessions_redis,
        )
        return await list_org_sessions_redis(org_id, db_fallback_fn)

    async def _idle_monitor_loop(self) -> None:
        from services.online_collab.core.online_collab_idle_monitor import (
            idle_monitor_loop,
        )

        await idle_monitor_loop(self)


# ---------------------------------------------------------------------------
# Singleton accessor and startup helper
# ---------------------------------------------------------------------------

class _OnlineCollabManagerSingleton:
    """Module-private holder so the accessor doesn't need a module-level global."""

    instance: Optional[OnlineCollabManager] = None


def get_online_collab_manager() -> OnlineCollabManager:
    """Return the singleton OnlineCollabManager (created on first call)."""
    if _OnlineCollabManagerSingleton.instance is None:
        _OnlineCollabManagerSingleton.instance = OnlineCollabManager()
    return _OnlineCollabManagerSingleton.instance


def start_online_collab_manager() -> asyncio.Task:  # type: ignore[type-arg]
    """
    Launch the idle monitor background task.

    The task is pinned via a strong reference on the manager instance to
    prevent GC cancellation (no wrapper needed — manager outlives the task).
    Call once from the FastAPI lifespan. Cancel the returned Task on shutdown.
    """
    mgr = get_online_collab_manager()
    task: asyncio.Task = asyncio.create_task(  # type: ignore[type-arg]
        mgr._idle_monitor_loop(),
        name="workshop_idle_monitor",
    )
    mgr._idle_monitor_task = task
    logger.info("[OnlineCollabMgr] Idle monitor task created")
    return task
