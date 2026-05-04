"""
Workshop status and organization-listing queries.

Extracted from ``WorkshopService`` to keep file sizes within limit.

Copyright 2024-2025 鍖椾含鎬濇簮鏅烘暀绉戞妧鏈夐檺鍏徃 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional, Tuple

from redis.exceptions import RedisError
from sqlalchemy import or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import AsyncSessionLocal
from models.domain.auth import User
from models.domain.diagrams import Diagram
from services.redis.redis_async_client import get_async_redis
from services.online_collab.lifecycle.session_meta_cache import get_session_meta_cached
from services.online_collab.lifecycle.online_collab_expiry import is_online_collab_expired, remaining_seconds
from services.online_collab.participant.online_collab_participant_ops import participant_count_for_code
from services.online_collab.redis.online_collab_redis_keys import participants_key
from services.online_collab.lifecycle.online_collab_session_fields import backfill_online_collab_expiry_if_needed
from services.online_collab.lifecycle.online_collab_visibility_helpers import (
    ONLINE_COLLAB_VISIBILITY_NETWORK,
    ONLINE_COLLAB_VISIBILITY_ORGANIZATION,
    ONLINE_COLLAB_VISIBILITY_PRIVATE,
    clear_expired_online_collab_session,
    diagram_online_collab_visibility,
    viewer_may_see_online_collab_code,
)

logger = logging.getLogger(__name__)


async def _redis_participant_counts(codes: List[str]) -> Dict[str, int] | None:
    """Pipeline HLEN participant counts for SQL fallback rows."""
    redis = get_async_redis()
    if not redis:
        return None
    try:
        async with redis.pipeline(transaction=False) as pipe:
            for code in codes:
                pipe.hlen(participants_key(code))
            values = await pipe.execute()
        return {
            code: int(values[idx])
            for idx, code in enumerate(codes)
        }
    except (RedisError, OSError, TypeError, ValueError):
        return None


async def _sql_list_org_sessions_by_org_id(
    org_id: int,
) -> List[Dict[str, Any]]:
    """
    SQL fallback: return active org workshops by org_id with Redis participant-count
    filter.  Mirrors the original list_org_online_collab_sessions_for_user logic.

    Includes sessions from org-less hosts (organization_id IS NULL) so that
    admin/superuser-hosted sessions are still discoverable when Redis is unavailable.
    """
    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(
                select(Diagram, User)
                .join(User, User.id == Diagram.user_id)
                .filter(
                    ~Diagram.is_deleted,
                    Diagram.workshop_code.isnot(None),
                    or_(
                        User.organization_id == org_id,
                        User.organization_id.is_(None),
                    ),
                    or_(
                        Diagram.workshop_visibility.is_(None),
                        Diagram.workshop_visibility == ONLINE_COLLAB_VISIBILITY_ORGANIZATION,
                    ),
                    or_(
                        Diagram.workshop_expires_at.is_(None),
                        Diagram.workshop_expires_at > datetime.now(UTC),
                    ),
                )
            )
            rows = result.all()
            out: List[Dict[str, Any]] = []
            codes = [
                str(diagram.workshop_code).strip().upper()
                for diagram, _owner in rows
                if diagram.workshop_code
            ]
            counts = await _redis_participant_counts(codes)
            for diagram, owner in rows:
                code = diagram.workshop_code
                if not code:
                    continue
                norm_code = code.strip().upper()
                count = counts.get(norm_code) if counts is not None else None
                if count is not None and count == 0:
                    continue
                rem = remaining_seconds(diagram.workshop_expires_at)
                out.append(
                    {
                        "diagram_id": diagram.id,
                        "title": diagram.title,
                        "owner_name": owner.name or None,
                        "participant_count": count if count is not None else 0,
                        "expires_at": (
                            diagram.workshop_expires_at.isoformat() + "Z"
                            if diagram.workshop_expires_at
                            else None
                        ),
                        "remaining_seconds": rem,
                    }
                )
            return out
        except (SQLAlchemyError, OSError) as exc:
            logger.error(
                "[OnlineCollabStatusOps] _sql_list_org_sessions_by_org_id: %s",
                exc,
                exc_info=True,
            )
            return []


async def list_org_online_collab_sessions_for_user(
    user_id: int,
) -> List[Dict[str, Any]]:
    """
    Return active workshops visible to *user_id* within the same organization (鏍″唴 list).

    Uses manager.list_org_sessions (Redis-first) with a SQL fallback when Redis
    is unavailable or the registry set is empty (e.g., immediately after a fresh
    deployment before any new sessions are registered).
    """
    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(select(User).filter(User.id == user_id))
            viewer = result.scalars().first()
            if not viewer or viewer.organization_id is None:
                return []
            org_id = viewer.organization_id
        except (SQLAlchemyError, OSError) as exc:
            logger.error(
                "[OnlineCollabStatusOps] list_org_online_collab_sessions: user lookup: %s",
                exc,
                exc_info=True,
            )
            return []

    from services.online_collab.core.online_collab_manager import (
        get_online_collab_manager,
    )

    async def _db_fallback() -> List[Dict[str, Any]]:
        return await _sql_list_org_sessions_by_org_id(org_id)

    return await get_online_collab_manager().list_org_sessions(
        org_id, db_fallback_fn=_db_fallback
    )


async def _redis_visibility_for_code(code: str) -> Optional[str]:
    """
    Short-circuit visibility lookup via the cached session_meta HASH.

    Uses the process-local :func:`get_session_meta_cached` read-through cache
    so repeat reads (join handshake, idle monitor, status endpoint) don't pay
    a round-trip each. Returns ``None`` when the session is not live so
    callers can fall back to the DB query.
    """
    if not code:
        return None
    meta = await get_session_meta_cached(code)
    if not meta:
        return None
    vis = (meta.get("visibility") or "").strip()
    if vis == ONLINE_COLLAB_VISIBILITY_NETWORK:
        return ONLINE_COLLAB_VISIBILITY_NETWORK
    if vis == ONLINE_COLLAB_VISIBILITY_ORGANIZATION:
        return ONLINE_COLLAB_VISIBILITY_ORGANIZATION
    if vis == ONLINE_COLLAB_VISIBILITY_PRIVATE:
        return ONLINE_COLLAB_VISIBILITY_PRIVATE
    return None


async def online_collab_visibility_for_diagram_id(
    diagram_id: str,
    code: Optional[str] = None,
) -> str:
    """
    Return canonical workshop_visibility for diagram (for WS join payloads).

    When ``code`` is known by the caller (e.g., WS context), the Redis
    ``session_meta`` HASH is consulted first 鈥?a single HGET that removes the
    DB round-trip on the hot join-handshake path. Falls back to
    ``Diagram.workshop_visibility`` when Redis is unavailable or no active
    session exists.
    """
    if code:
        cached = await _redis_visibility_for_code(code)
        if cached is not None:
            return cached
    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(
                select(Diagram.workshop_visibility).filter(
                    Diagram.id == diagram_id,
                    ~Diagram.is_deleted,
                )
            )
            row = result.first()
            if row is None:
                return ONLINE_COLLAB_VISIBILITY_PRIVATE
            vis = row[0]
            if vis == ONLINE_COLLAB_VISIBILITY_NETWORK:
                return ONLINE_COLLAB_VISIBILITY_NETWORK
            if vis == ONLINE_COLLAB_VISIBILITY_ORGANIZATION:
                return ONLINE_COLLAB_VISIBILITY_ORGANIZATION
            return ONLINE_COLLAB_VISIBILITY_PRIVATE
        except (SQLAlchemyError, OSError) as exc:
            logger.warning(
                "[OnlineCollabStatusOps] online_collab_visibility_for_diagram_id: %s",
                exc,
            )
            return ONLINE_COLLAB_VISIBILITY_PRIVATE


async def _compute_online_collab_status_for_viewer(
    db: AsyncSession,
    diagram: Diagram,
    viewer_user_id: int,
) -> Tuple[Optional[Dict[str, Any]], str]:
    """Compute status payload. Error is one of: ``''``, ``'not_found'``, ``'forbidden'``."""
    await backfill_online_collab_expiry_if_needed(diagram, db)
    redis = get_async_redis()
    if diagram.workshop_expires_at and is_online_collab_expired(diagram.workshop_expires_at):
        if redis:
            await clear_expired_online_collab_session(diagram, db, redis)
        await db.refresh(diagram)
        if diagram.user_id != viewer_user_id:
            return None, "forbidden"
        return {"active": False}, ""

    code = diagram.workshop_code
    if not code:
        if diagram.user_id != viewer_user_id:
            return None, "forbidden"
        return {"active": False}, ""

    count = await participant_count_for_code(code)
    vis = diagram_online_collab_visibility(diagram)

    if await viewer_may_see_online_collab_code(db, diagram, viewer_user_id):
        rem = remaining_seconds(diagram.workshop_expires_at)
        payload: Dict[str, Any] = {
            "active": True,
            "code": code,
            "participant_count": count,
            "workshop_visibility": vis,
            "is_owner": diagram.user_id == viewer_user_id,
            "expires_at": (
                diagram.workshop_expires_at.isoformat() + "Z"
                if diagram.workshop_expires_at
                else None
            ),
            "remaining_seconds": rem,
            "duration_preset": diagram.workshop_duration_preset,
        }
        return payload, ""
    return None, "forbidden"


async def get_online_collab_status_for_viewer(
    diagram_id: str,
    viewer_user_id: int,
) -> Tuple[Optional[Dict[str, Any]], str]:
    """
    Return ``(payload, error)`` for a diagram's workshop status.

    *error* is one of ``''`` (success), ``'not_found'``, or ``'forbidden'``.
    """
    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(
                select(Diagram).filter(
                    Diagram.id == diagram_id,
                    ~Diagram.is_deleted,
                )
            )
            diagram = result.scalars().first()
            if not diagram:
                return None, "not_found"
            return await _compute_online_collab_status_for_viewer(db, diagram, viewer_user_id)
        except (SQLAlchemyError, OSError) as exc:
            logger.error(
                "[OnlineCollabStatusOps] get_online_collab_status: %s",
                exc,
                exc_info=True,
            )
            return None, "not_found"


async def diagram_title_for_active_workshop(diagram_id: str) -> Optional[str]:
    """
    Persisted diagram title for collab handshake / session banners (never raises).
    """
    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(
                select(Diagram.title).where(
                    Diagram.id == diagram_id,
                    ~Diagram.is_deleted,
                )
            )
            raw_title = result.scalar_one_or_none()
        except (SQLAlchemyError, OSError) as exc:
            logger.debug(
                "[OnlineCollabStatusOps] diagram_title_for_active_workshop: %s",
                exc,
            )
            return None
    if raw_title is None:
        return None
    trimmed = str(raw_title).strip()
    return trimmed if trimmed else None
