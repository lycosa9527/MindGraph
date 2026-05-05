"""Owner and idle stop flows for online collaboration sessions."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from config.database import AsyncSessionLocal
from models.domain.diagrams import Diagram
from services.online_collab.lifecycle.online_collab_session_fields import (
    clear_online_collab_session_by_id_returning,
    clear_online_collab_session_fields,
)
from services.online_collab.redis.online_collab_redis_keys import (
    code_to_diagram_key,
    live_changed_keys_key,
    live_flush_pending_key,
    live_spec_key,
    session_key,
    session_meta_key,
)
from services.online_collab.spec.online_collab_live_spec_ops import (
    flush_live_spec_to_db_in_session,
    mark_live_spec_db_flushed,
)
from services.redis.cache.redis_diagram_cache import get_diagram_cache
from services.redis.redis_async_client import get_async_redis

logger = logging.getLogger(__name__)

_FAILED_FLUSH_RETRY_TTL_SEC = 15 * 60
WORKSHOP_STOP_FLUSH_MAX_ATTEMPTS = 5
_STOP_FLUSH_RETRY_INITIAL_DELAY_SEC = 0.06


async def _flush_live_spec_with_retries_for_stop(
    db: Any,
    redis: Any,
    code: str,
    diagram_id: str,
) -> bool:
    """Flush live Redis spec to Postgres; retry when another flush holds the PG lock."""
    for attempt in range(WORKSHOP_STOP_FLUSH_MAX_ATTEMPTS):
        ok = await flush_live_spec_to_db_in_session(db, redis, code, diagram_id)
        if ok:
            return True
        if attempt < WORKSHOP_STOP_FLUSH_MAX_ATTEMPTS - 1:
            delay = _STOP_FLUSH_RETRY_INITIAL_DELAY_SEC * (attempt + 1)
            await asyncio.sleep(delay)
    return False


async def _extend_room_ttl_after_flush_failure(redis: Any, code: str) -> None:
    """Keep room state around long enough for the next cleanup retry."""
    if redis is None:
        logger.error(
            "[OnlineCollabMgr] cannot extend room TTL after flush failure; "
            "Redis client missing code=%s",
            code,
        )
        return
    keys = (
        session_key(code),
        session_meta_key(code),
        code_to_diagram_key(code),
        live_spec_key(code),
        live_changed_keys_key(code),
        live_flush_pending_key(code),
    )
    try:
        async with redis.pipeline(transaction=False) as pipe:
            for key in keys:
                pipe.expire(key, _FAILED_FLUSH_RETRY_TTL_SEC, gt=True)
            await pipe.execute()
    except (RedisError, OSError, RuntimeError, TypeError) as exc:
        logger.error(
            "[OnlineCollabMgr] failed to extend room TTL after flush failure "
            "code=%s: %s",
            code, exc, exc_info=True,
        )


async def stop_online_collab_impl(diagram_id: str, user_id: int) -> bool:
    """Owner-initiated workshop stop."""
    async with AsyncSessionLocal() as db:
        try:
            owner_row = await db.execute(
                select(Diagram.user_id, Diagram.workshop_code).where(
                    Diagram.id == diagram_id,
                    ~Diagram.is_deleted,
                )
            )
            row = owner_row.one_or_none()
            if row is None:
                return False
            owner_id, code = row[0], row[1]
            if owner_id != user_id:
                return False
            if not code or not str(code).strip():
                logger.debug(
                    "[OnlineCollabMgr] stop_online_collab: already inactive "
                    "diagram=%s user=%s",
                    diagram_id,
                    user_id,
                )
                return True
            norm = str(code).strip().upper()
            from services.online_collab.lifecycle.online_collab_session_closing import (
                mark_workshop_session_closing,
                unmark_workshop_session_closing,
            )
            from routers.api.workshop_ws_broadcast import (
                broadcast_workshop_session_closing,
            )

            await mark_workshop_session_closing(norm)
            await broadcast_workshop_session_closing(norm)
            await asyncio.sleep(0.05)

            redis = get_async_redis()
            flush_ok = await _flush_live_spec_with_retries_for_stop(
                db, redis, norm, diagram_id,
            )
            if not flush_ok:
                logger.error(
                    "[OnlineCollabMgr] stop_online_collab flush failed; "
                    "refusing to clear/destroy session code=%s diagram=%s",
                    norm, diagram_id,
                )
                await _extend_room_ttl_after_flush_failure(redis, norm)
                await unmark_workshop_session_closing(norm)
                await db.rollback()
                return False

            cleared = await clear_online_collab_session_by_id_returning(
                db, diagram_id,
            )
            if cleared is None:
                await db.rollback()
                return False
            try:
                await db.commit()
            except SQLAlchemyError:
                await db.rollback()
                raise
            await mark_live_spec_db_flushed(redis, norm)

            from routers.api.workshop_ws_broadcast import (
                broadcast_workshop_session_ended,
            )
            await broadcast_workshop_session_ended(code)
            await asyncio.sleep(0.08)

            from services.online_collab.core.online_collab_manager import (
                get_online_collab_manager,
            )
            await get_online_collab_manager().destroy_session(
                norm, reason="explicit", diagram_id=diagram_id,
            )

            logger.info(
                "[OnlineCollabMgr] Stopped workshop %s for diagram %s",
                code, diagram_id,
            )
            try:
                await get_diagram_cache().invalidate_user_list(user_id)
            except (AttributeError, TypeError, ValueError, OSError, RuntimeError) as cache_exc:
                logger.debug(
                    "[OnlineCollabMgr] List cache invalidation failed "
                    "(non-fatal): %s", cache_exc,
                )
            return True

        except (SQLAlchemyError, OSError) as exc:
            logger.error(
                "[OnlineCollabMgr] Error stopping workshop: %s",
                exc, exc_info=True,
            )
            await db.rollback()
            return False


async def stop_online_collab_for_room_idle_impl(
    diagram_id: str,
    expected_code: str,
) -> bool:
    """Idle-timer initiated stop with expected-code protection."""
    norm = expected_code.strip().upper()
    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(
                select(Diagram).filter(
                    Diagram.id == diagram_id,
                    ~Diagram.is_deleted,
                )
            )
            diagram = result.scalars().first()
            if not diagram or not diagram.workshop_code:
                return False
            row_code = diagram.workshop_code.strip().upper()
            if row_code != norm:
                logger.warning(
                    "[OnlineCollabMgr] Idle stop code mismatch diagram=%s",
                    diagram_id,
                )
                return False

            from services.online_collab.lifecycle.online_collab_session_closing import (
                mark_workshop_session_closing,
                unmark_workshop_session_closing,
            )
            from routers.api.workshop_ws_broadcast import (
                broadcast_workshop_session_closing,
            )

            await mark_workshop_session_closing(norm)
            await broadcast_workshop_session_closing(norm)
            await asyncio.sleep(0.05)

            ws_code = diagram.workshop_code
            redis = get_async_redis()
            flush_ok = await _flush_live_spec_with_retries_for_stop(
                db, redis, norm, diagram_id,
            )
            if not flush_ok:
                logger.error(
                    "[OnlineCollabMgr] Idle-stop flush failed; refusing to "
                    "destroy session code=%s diagram=%s",
                    ws_code, diagram_id,
                )
                await _extend_room_ttl_after_flush_failure(redis, norm)
                await unmark_workshop_session_closing(norm)
                await db.rollback()
                return False

            from services.online_collab.core.online_collab_manager import (
                get_online_collab_manager,
            )
            redis_ok = True
            try:
                await get_online_collab_manager().destroy_session(
                    norm, reason="idle", diagram_id=diagram_id,
                )
            except (RedisError, OSError, RuntimeError, TypeError) as redis_exc:
                redis_ok = False
                logger.error(
                    "[OnlineCollabMgr] Idle-stop destroy_session Redis "
                    "failure code=%s diagram=%s: %s",
                    ws_code, diagram_id, redis_exc, exc_info=True,
                )

            if not redis_ok:
                logger.warning(
                    "[OnlineCollabMgr] Idle-stop aborted (Redis down); "
                    "leaving DB session fields intact for cleanup "
                    "compensation code=%s diagram=%s",
                    ws_code, diagram_id,
                )
                await db.rollback()
                return False

            clear_online_collab_session_fields(diagram)
            try:
                await db.commit()
            except SQLAlchemyError:
                await db.rollback()
                raise
            await mark_live_spec_db_flushed(redis, norm)

            logger.info(
                "[OnlineCollabMgr] Idle-stop workshop %s for diagram %s",
                ws_code, diagram_id,
            )
            return True

        except (SQLAlchemyError, OSError, RedisError) as exc:
            logger.error(
                "[OnlineCollabMgr] Error idle-stopping workshop: %s",
                exc, exc_info=True,
            )
            await db.rollback()
            return False
