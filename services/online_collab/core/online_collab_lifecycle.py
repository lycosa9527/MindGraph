"""
Workshop lifecycle (start / stop / idle-stop) extracted from workshop_service.

Kept as free functions rather than methods so the main ``WorkshopService``
stays thin (delegation only). All three call sites share the same Redis
ownership check, DB-row transition and fan-out broadcast flow 鈥?separating
them here keeps ``workshop_service.py`` under the per-file 600-800 line cap
dictated by the code-style rules.

Copyright 2024-2025 Beijing Siyuan Zhijiao Technology Co., Ltd.
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Optional, Tuple

from redis.exceptions import RedisError
from sqlalchemy import select, text as sql_text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from config.database import AsyncSessionLocal
from models.domain.auth import User
from models.domain.diagrams import Diagram
from services.redis.cache.redis_diagram_cache import get_diagram_cache
from services.redis.redis_async_client import get_async_redis
from services.infrastructure.monitoring.ws_metrics import record_ws_cleanup_partition_size
from services.online_collab.lifecycle.online_collab_expiry import (
    DURATION_TODAY,
    compute_online_collab_expires_at,
    expires_at_to_unix,
    is_online_collab_expired,
    redis_ttl_seconds_for_expires_at,
)
from services.online_collab.lifecycle.online_collab_session_fields import (
    clear_online_collab_session_by_id_returning,
    clear_online_collab_session_fields,
)
from services.online_collab.lifecycle.online_collab_visibility_helpers import (
    ONLINE_COLLAB_VISIBILITY_ORGANIZATION,
)
from services.online_collab.redis.online_collab_redis_keys import (
    code_to_diagram_key,
    purge_online_collab_redis_keys,
    registry_global_org_key,
    registry_org_key,
    session_key,
    session_meta_key,
    start_lock_key,
)
from services.online_collab.redis.online_collab_redis_locks import (
    acquire_nx_lock,
    extend_nx_lock,
    new_lock_token,
    release_nx_lock,
)

logger = logging.getLogger(__name__)

ONLINE_COLLAB_SESSION_TTL_CAP_SEC = 86400 * 14


_CLEANUP_LOCK_KEY = "workshop:cleanup_lock"
_CLEANUP_LOCK_TTL_SEC = 15 * 60  # 15 min ceiling; heartbeat extends if needed
_CLEANUP_LOCK_HEARTBEAT_SEC = 5 * 60  # extend every 5 min while working


async def _cleanup_lock_heartbeat(token: str, stop_event: asyncio.Event) -> None:
    """Extend the cleanup NX lock while cleanup_expired_online_collabs_impl runs."""
    redis = get_async_redis()
    if not redis:
        return
    try:
        while not stop_event.is_set():
            try:
                await asyncio.wait_for(
                    stop_event.wait(), timeout=_CLEANUP_LOCK_HEARTBEAT_SEC,
                )
                return
            except asyncio.TimeoutError:
                pass
            try:
                extended = await extend_nx_lock(
                    redis, _CLEANUP_LOCK_KEY, token, _CLEANUP_LOCK_TTL_SEC,
                )
            except (RedisError, OSError, RuntimeError, TypeError) as exc:
                logger.debug(
                    "[OnlineCollabCleanup] Lock extend failed: %s", exc,
                )
                return
            if not extended:
                logger.warning(
                    "[OnlineCollabCleanup] Lost cleanup lock (ownership changed); "
                    "stopping heartbeat"
                )
                return
    except asyncio.CancelledError:
        return


async def cleanup_expired_online_collabs_impl() -> int:
    """
    Clear diagrams whose ``workshop_expires_at`` is in the past.

    Uses a short 15-minute NX lock with ownership-verified CAS release and a
    5-minute heartbeat so a crashed worker cannot block the next run for
    7 hours (the previous TTL). The heartbeat extends the lock while cleanup
    is still running; on crash the lock expires quickly and another worker
    can proceed.
    """
    redis = get_async_redis()
    if not redis:
        logger.error("[OnlineCollabCleanup] Redis client not available")
        return 0

    lock_token: str = ""
    try:
        acquired_token = await acquire_nx_lock(
            redis, _CLEANUP_LOCK_KEY, _CLEANUP_LOCK_TTL_SEC, new_lock_token(),
        )
        if acquired_token is not None:
            lock_token = acquired_token
    except (RedisError, OSError, RuntimeError, TypeError) as lock_exc:
        logger.warning(
            "[OnlineCollabCleanup] Could not acquire cleanup lock: %s — skipping run",
            lock_exc,
        )
        return 0

    if not lock_token:
        logger.debug(
            "[OnlineCollabCleanup] Skipped - another worker holds the cleanup lock"
        )
        return 0

    stop_heartbeat = asyncio.Event()
    heartbeat_task: asyncio.Task | None = None
    if lock_token:
        heartbeat_task = asyncio.create_task(
            _cleanup_lock_heartbeat(lock_token, stop_heartbeat),
            name="workshop_cleanup_lock_heartbeat",
        )

    cleaned_count = 0
    try:
        async with AsyncSessionLocal() as db:
            try:
                # PG 18: set lock_timeout so the MERGE cannot block indefinitely
                # waiting for a row-level lock held by a concurrent editor.
                # 5 s is generous; cleanup can retry on the next scheduler run.
                await db.execute(sql_text("SET LOCAL lock_timeout = '5000ms'"))
                now = datetime.now(UTC)
                legacy_cutoff_stmt = select(Diagram.id).where(
                    Diagram.workshop_code.isnot(None),
                    ~Diagram.is_deleted,
                    Diagram.workshop_expires_at.is_(None),
                )
                # MERGE: match expired workshops once and clear in one statement.
                # s.workshop_code is the pre-update value so Redis can be purged
                # correctly — an UPDATE...RETURNING would see the post-update NULL.
                merge_stmt = sql_text("""
MERGE INTO diagrams AS t
USING (
    SELECT id, workshop_code
    FROM   diagrams
    WHERE  workshop_code     IS NOT NULL
      AND  NOT is_deleted
      AND  workshop_expires_at IS NOT NULL
      AND  workshop_expires_at <= :now
) AS s ON t.id = s.id
WHEN MATCHED THEN
    UPDATE SET
        workshop_code            = NULL,
        workshop_visibility      = NULL,
        workshop_started_at      = NULL,
        workshop_expires_at      = NULL,
        workshop_duration_preset = NULL
RETURNING t.id, s.workshop_code
""")
                merge_result = await db.execute(merge_stmt, {"now": now})
                rows = merge_result.all()
                cleared_ids = [r[0] for r in rows]

                legacy_rows = await db.execute(legacy_cutoff_stmt)
                legacy_ids = [row[0] for row in legacy_rows.all()]

                codes_to_purge: list[str] = [r[1] for r in rows if r[1]]

                await db.commit()
                cleaned_count = len(cleared_ids)
                record_ws_cleanup_partition_size(cleaned_count)

                if codes_to_purge:
                    purge_sem = asyncio.Semaphore(10)

                    async def _purge_one(c: str) -> None:
                        async with purge_sem:
                            try:
                                await purge_online_collab_redis_keys(redis, c)
                            except (RedisError, OSError, RuntimeError, TypeError) as exc:
                                logger.warning(
                                    "[OnlineCollabCleanup] Redis purge failed "
                                    "code=%s: %s", c, exc,
                                )

                    await asyncio.gather(
                        *[_purge_one(c) for c in codes_to_purge],
                        return_exceptions=True,
                    )

                if legacy_ids:
                    from services.online_collab.lifecycle.online_collab_session_fields import (
                        backfill_online_collab_expiry_if_needed,
                    )
                    legacy_result = await db.execute(
                        select(Diagram).where(Diagram.id.in_(legacy_ids))
                    )
                    legacy_diagrams = legacy_result.scalars().all()
                    for diagram in legacy_diagrams:
                        await backfill_online_collab_expiry_if_needed(diagram, db)
                        if (
                            diagram.workshop_expires_at
                            and is_online_collab_expired(
                                diagram.workshop_expires_at,
                            )
                            and diagram.workshop_code
                        ):
                            legacy_code = diagram.workshop_code
                            diagram.workshop_code = None
                            diagram.workshop_visibility = None
                            diagram.workshop_started_at = None
                            diagram.workshop_expires_at = None
                            diagram.workshop_duration_preset = None
                            cleaned_count += 1
                            try:
                                await purge_online_collab_redis_keys(
                                    redis, legacy_code,
                                )
                            except (RedisError, OSError, RuntimeError, TypeError) as exc:
                                logger.warning(
                                    "[OnlineCollabCleanup] Redis purge failed "
                                    "legacy code=%s: %s",
                                    legacy_code,
                                    exc,
                                )
                    if legacy_diagrams:
                        await db.commit()

                if cleaned_count > 0:
                    logger.info(
                        "[OnlineCollabCleanup] Cleaned up %d expired workshop(s)",
                        cleaned_count,
                    )

            except (SQLAlchemyError, RedisError, OSError, RuntimeError, TypeError, ValueError) as exc:
                logger.error(
                    "[OnlineCollabCleanup] Error cleaning up expired workshops: %s",
                    exc,
                    exc_info=True,
                )
                await db.rollback()
    finally:
        stop_heartbeat.set()
        if heartbeat_task is not None:
            try:
                await asyncio.wait_for(heartbeat_task, timeout=2.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                heartbeat_task.cancel()
        if lock_token:
            try:
                await release_nx_lock(redis, _CLEANUP_LOCK_KEY, lock_token)
            except (RedisError, OSError, RuntimeError, TypeError) as exc:
                logger.debug(
                    "[OnlineCollabCleanup] Lock release failed (will expire): %s",
                    exc,
                )

    return cleaned_count


async def start_online_collab_impl(
    allocate_unique_code,
    validation_error,
    session_redis_value,
    diagram_id: str,
    user_id: int,
    visibility: str,
    duration: str,
    workshop_session_ttl: int,
    target_org_id: Optional[int] = None,
) -> Tuple[Optional[str], Optional[str], Optional[datetime], int]:
    """
    Create (or return existing) workshop session for ``diagram_id``.

    Parameters
    ----------
    allocate_unique_code : Callable[[redis], Awaitable[Optional[str]]]
        Injected to keep the XXX-XXX generator and collision check local to
        the parent ``WorkshopService``.
    validation_error : Callable[...]
        Injected pre-condition check (duration, visibility, ownership).
    session_redis_value : Callable[...]
        Produces the JSON blob written to ``session:{code}``.

    Returns
    -------
    (code, error, expires_at, stopped_previous_sessions)
        Exactly one of ``code`` or ``error`` is set. The fourth field counts
        other diagrams stopped to enforce single hosted session per owner.
        It is ``0`` on error paths prior to teardown.
    """
    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(
                select(Diagram).filter(
                    Diagram.id == diagram_id,
                    Diagram.user_id == user_id,
                    ~Diagram.is_deleted,
                )
            )
            diagram = result.scalars().first()

            verr = validation_error(
                diagram, diagram_id, user_id, visibility, duration,
            )
            if verr:
                return None, verr, None, 0
            if diagram is None:
                return (
                    None,
                    f"Diagram {diagram_id} not found or not owned by user {user_id}",
                    None,
                    0,
                )

            redis = get_async_redis()
            if not redis:
                error_msg = (
                    "Redis client not available. "
                    "Presentation mode requires Redis."
                )
                logger.error("[OnlineCollabMgr] %s", error_msg)
                return None, error_msg, None, 0

            start_lock_token = await acquire_nx_lock(
                redis, start_lock_key(diagram_id), 30,
            )
            lock_acquired = start_lock_token is not None
            if not lock_acquired:
                logger.info(
                    "[OnlineCollabMgr] start_online_collab: another worker holds "
                    "start_lock for diagram_id=%s, re-checking DB",
                    diagram_id,
                )
                await asyncio.sleep(0.3)
                try:
                    await db.refresh(diagram)
                except SQLAlchemyError:
                    pass
                if diagram.workshop_code and not (
                    diagram.workshop_expires_at
                    and is_online_collab_expired(diagram.workshop_expires_at)
                ):
                    return (
                        diagram.workshop_code,
                        None,
                        diagram.workshop_expires_at,
                        0,
                    )
                return (
                    None,
                    "Collaboration session is being initialised, please retry",
                    None,
                    0,
                )

            from services.online_collab.lifecycle.online_collab_single_owner_session import (
                stop_other_owner_online_collabs,
            )

            stopped_prior_sessions = await stop_other_owner_online_collabs(
                owner_user_id=user_id,
                except_diagram_id=diagram_id,
            )

            owner_name = ""
            org_id: Optional[int] = None
            try:
                user_result = await db.execute(
                    select(User).filter(User.id == user_id),
                )
                owner = user_result.scalars().first()
                if owner:
                    owner_name = owner.name or ""
                    org_id = owner.organization_id
            except SQLAlchemyError as user_exc:
                logger.warning(
                    "[OnlineCollabMgr] Could not fetch owner for session "
                    "registry user_id=%s: %s", user_id, user_exc,
                )

            if org_id is None and target_org_id is not None:
                org_id = target_org_id
                logger.debug(
                    "[OnlineCollabMgr] Using caller-supplied target_org_id=%s "
                    "for session registry (owner user_id=%s has no org)",
                    org_id, user_id,
                )

            if diagram.workshop_code and not (
                diagram.workshop_expires_at
                and is_online_collab_expired(diagram.workshop_expires_at)
            ):
                existing_code = diagram.workshop_code
                redis_alive = False
                try:
                    redis_alive = bool(
                        await redis.exists(session_meta_key(existing_code))
                    )
                except (RedisError, OSError, RuntimeError, TypeError):
                    pass
                if redis_alive:
                    logger.info(
                        "[OnlineCollabMgr] Diagram %s already has active "
                        "session %s, returning existing code",
                        diagram_id, existing_code,
                    )
                    try:
                        async with redis.pipeline(transaction=False) as reg_pipe:
                            if org_id is not None:
                                reg_pipe.sadd(registry_org_key(org_id), existing_code)
                            elif visibility == "organization":
                                reg_pipe.sadd(registry_global_org_key(), existing_code)
                            await reg_pipe.execute()
                    except (RedisError, OSError, RuntimeError, TypeError) as reg_exc:
                        logger.warning(
                            "[OnlineCollabMgr] Could not re-register existing "
                            "session code=%s in org registry: %s",
                            existing_code, reg_exc,
                        )
                    await release_nx_lock(
                        redis, start_lock_key(diagram_id), start_lock_token,
                    )
                    return (
                        existing_code,
                        None,
                        diagram.workshop_expires_at,
                        stopped_prior_sessions,
                    )

                logger.warning(
                    "[OnlineCollabMgr] Stale DB session detected code=%s "
                    "diagram_id=%s: no Redis session_meta, clearing and "
                    "creating fresh session",
                    existing_code, diagram_id,
                )
                clear_online_collab_session_fields(diagram)
                try:
                    await db.commit()
                except SQLAlchemyError:
                    await db.rollback()
                    await release_nx_lock(
                        redis, start_lock_key(diagram_id), start_lock_token,
                    )
                    raise

            code: Optional[str] = None
            started_at: Optional[datetime] = None
            expires_at: Optional[datetime] = None
            ttl_sec = 0
            for attempt in range(1, 6):
                code = await allocate_unique_code(redis)
                if not code:
                    error_msg = (
                        "Failed to generate unique presentation code "
                        "after multiple attempts"
                    )
                    logger.error("[OnlineCollabMgr] %s", error_msg)
                    await release_nx_lock(
                        redis, start_lock_key(diagram_id), start_lock_token,
                    )
                    return None, error_msg, None, stopped_prior_sessions
                code = code.strip().upper()
                started_at = datetime.now(UTC)
                expires_at = compute_online_collab_expires_at(started_at, duration)
                ttl_sec = redis_ttl_seconds_for_expires_at(expires_at)
                ttl_sec = min(
                    max(ttl_sec, 1), workshop_session_ttl * 14,
                )

                if org_id is None and visibility == "organization":
                    logger.debug(
                        "[OnlineCollabMgr] Starting org-visibility session for "
                        "user_id=%s who has no organization_id (admin/superuser host). "
                        "Session code=%s will be registered in the global org registry "
                        "and visible to all org members.",
                        user_id, code,
                    )

                diagram.workshop_code = code
                diagram.workshop_visibility = visibility
                diagram.workshop_started_at = started_at
                diagram.workshop_expires_at = expires_at
                diagram.workshop_duration_preset = duration
                try:
                    await db.commit()
                    break
                except IntegrityError as int_exc:
                    await db.rollback()
                    await db.refresh(diagram)
                    logger.warning(
                        "[OnlineCollabMgr] workshop_code collision code=%s "
                        "diagram=%s attempt=%s: %s",
                        code, diagram_id, attempt, int_exc,
                    )
                    if attempt >= 5:
                        raise
                    diagram.workshop_code = None
                except SQLAlchemyError:
                    await db.rollback()
                    raise
            if code is None or started_at is None or expires_at is None:
                error_msg = "Failed to persist collaboration session code"
                logger.error("[OnlineCollabMgr] %s", error_msg)
                await release_nx_lock(
                    redis, start_lock_key(diagram_id), start_lock_token,
                )
                return None, error_msg, None, stopped_prior_sessions

            diagram_title = diagram.title or ""
            try:
                await db.close()
            except SQLAlchemyError as close_exc:
                logger.debug(
                    "[OnlineCollabMgr] Early db.close failed (non-fatal): %s",
                    close_exc,
                )

            try:
                await redis.setex(
                    session_key(code),
                    ttl_sec,
                    session_redis_value(diagram_id, user_id, started_at),
                )
                await redis.setex(
                    code_to_diagram_key(code), ttl_sec, diagram_id,
                )

                from services.online_collab.core.online_collab_manager import (
                    get_online_collab_manager,
                )
                await get_online_collab_manager().create_session(
                    code=code,
                    diagram_id=diagram_id,
                    owner_id=user_id,
                    org_id=org_id,
                    visibility=visibility,
                    expires_at_unix=expires_at_to_unix(expires_at),
                    ttl_sec=ttl_sec,
                    title=diagram_title,
                    owner_name=owner_name,
                )
            except (RedisError, OSError, RuntimeError, TypeError) as redis_exc:
                logger.error(
                    "[OnlineCollabMgr] Redis init failed for workshop %s, "
                    "rolling back DB session fields: %s",
                    code, redis_exc, exc_info=True,
                )
                try:
                    async with AsyncSessionLocal() as rollback_db:
                        await clear_online_collab_session_by_id_returning(
                            rollback_db, diagram_id,
                        )
                        await rollback_db.commit()
                except SQLAlchemyError as rb_exc:
                    logger.error(
                        "[OnlineCollabMgr] DB rollback after Redis failure "
                        "also failed diagram_id=%s: %s", diagram_id, rb_exc,
                    )
                await release_nx_lock(
                    redis, start_lock_key(diagram_id), start_lock_token,
                )
                return (
                    None,
                    "Failed to initialise collaboration session (Redis error)",
                    None,
                    stopped_prior_sessions,
                )

            logger.info(
                "[OnlineCollabMgr] Started workshop %s for diagram %s "
                "(user %s)", code, diagram_id, user_id,
            )
            await release_nx_lock(
                redis, start_lock_key(diagram_id), start_lock_token,
            )
            try:
                await get_diagram_cache().invalidate_user_list(user_id)
            except (AttributeError, TypeError, ValueError, OSError, RuntimeError) as cache_exc:
                logger.debug(
                    "[OnlineCollabMgr] List cache invalidation failed "
                    "(non-fatal): %s", cache_exc,
                )
            return code, None, expires_at, stopped_prior_sessions

        except (SQLAlchemyError, OSError) as exc:
            error_msg = f"Error starting presentation mode: {str(exc)}"
            logger.error(
                "[OnlineCollabMgr] %s", error_msg, exc_info=True,
            )
            try:
                await db.rollback()
            except SQLAlchemyError as rb_exc:
                logger.debug(
                    "[OnlineCollabMgr] rollback on closed session: %s",
                    rb_exc,
                )
            return None, error_msg, None, 0


async def stop_online_collab_impl(diagram_id: str, user_id: int) -> bool:
    """Owner-initiated workshop stop."""
    from services.online_collab.core.online_collab_stop import (
        stop_online_collab_impl as _impl,
    )
    return await _impl(diagram_id, user_id)


async def stop_online_collab_for_room_idle_impl(
    diagram_id: str,
    expected_code: str,
) -> bool:
    """Idle-timer initiated stop with expected-code protection."""
    from services.online_collab.core.online_collab_stop import (
        stop_online_collab_for_room_idle_impl as _impl,
    )
    return await _impl(diagram_id, expected_code)


__all__ = [
    "DURATION_TODAY",
    "ONLINE_COLLAB_VISIBILITY_ORGANIZATION",
    "cleanup_expired_online_collabs_impl",
    "start_online_collab_impl",
    "stop_online_collab_for_room_idle_impl",
    "stop_online_collab_impl",
]
