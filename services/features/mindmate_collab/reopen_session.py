"""
Reopen a finished MindMate seminar as the same live room.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import select, update

from models.domain.auth import User
from models.domain.mindmate_collab import MindmateCollabSession
from services.auth.expert_school_binding import bound_org_ids_for_user
from services.features.mindmate_collab.config import (
    MINDMATE_COLLAB_DEFAULT_DURATION,
    MINDMATE_COLLAB_MAX_ORG_CONCURRENT_SESSIONS,
)
from services.features.mindmate_collab.manager_access import get_mindmate_collab_manager
from services.features.mindmate_collab.member_record import record_collab_member
from services.features.mindmate_collab.redis_keys import start_lock_key
from services.online_collab.lifecycle.online_collab_expiry import (
    compute_online_collab_expires_at,
    duration_allowed_for_visibility,
    is_online_collab_expired,
)
from services.online_collab.lifecycle.online_collab_visibility_helpers import (
    ONLINE_COLLAB_VISIBILITY_ORGANIZATION,
)
from services.online_collab.redis.online_collab_redis_locks import (
    acquire_nx_lock,
    new_lock_token,
    release_nx_lock,
)
from services.redis.redis_async_client import get_async_redis
from utils.db.session_open import system_rls_session, user_rls_session


def reopen_block_reason(
    *,
    owner_user_id: int,
    actor_user_id: int,
    library_saved_at: Optional[datetime],
) -> Optional[str]:
    """Return why this person cannot continue the seminar, or None when they can."""
    if owner_user_id != actor_user_id:
        return "not_owner"
    if library_saved_at is None:
        return "not_saved"
    return None


def reopen_duration(visibility: str, duration_preset: str) -> str:
    """Keep the seminar's duration when it is still valid for that visibility."""
    preset = (duration_preset or "").strip() or MINDMATE_COLLAB_DEFAULT_DURATION
    if duration_allowed_for_visibility(visibility, preset):
        return preset
    return MINDMATE_COLLAB_DEFAULT_DURATION


def _room_payload(session: MindmateCollabSession, expires_at: datetime) -> Dict[str, Any]:
    label = expires_at.isoformat()
    if expires_at.tzinfo is None and not label.endswith("Z"):
        label = f"{label}Z"
    return {
        "session_id": session.id,
        "code": session.code,
        "visibility": session.visibility,
        "title": session.title,
        "owner_user_id": session.owner_user_id,
        "expires_at": label,
    }


async def _load_session(session_id: str) -> Optional[MindmateCollabSession]:
    async with system_rls_session() as db:
        session = (
            await db.execute(
                select(MindmateCollabSession).where(MindmateCollabSession.id == session_id),
            )
        ).scalar_one_or_none()
        if session is not None:
            db.expunge(session)
        return session


async def _set_ended_at(
    session_id: str,
    ended_at: Optional[datetime],
    expires_at: Optional[datetime],
) -> None:
    async with system_rls_session() as db:
        await db.execute(
            update(MindmateCollabSession)
            .where(MindmateCollabSession.id == session_id)
            .values(ended_at=ended_at, expires_at=expires_at),
        )
        await db.commit()


async def reopen_saved_seminar(
    session_id: str,
    user_id: int,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Make a saved seminar live again on its existing invite code."""
    redis = get_async_redis()
    if not redis:
        return None, "Collaboration service unavailable"

    lock_token = new_lock_token()
    lock_key = start_lock_key(user_id)
    acquired = await acquire_nx_lock(redis, lock_key, 30, lock_token)
    if not acquired:
        return None, "Please retry starting the room"

    try:
        return await _reopen_locked(session_id, user_id)
    finally:
        await release_nx_lock(redis, lock_key, lock_token)


async def _reopen_locked(
    session_id: str,
    user_id: int,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    session = await _load_session(session_id)
    if session is None:
        return None, "not_found"
    reason = reopen_block_reason(
        owner_user_id=session.owner_user_id,
        actor_user_id=user_id,
        library_saved_at=session.library_saved_at,
    )
    if reason:
        return None, reason

    async with user_rls_session(user_id) as db:
        user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
        if user is None:
            return None, "User not found"
        owner_name = user.name or user.phone or user.email or str(user_id)
        org_id = user.organization_id
        bound_org_ids = await bound_org_ids_for_user(db, user)

    manager = get_mindmate_collab_manager()
    already_live = session.ended_at is None
    previous_ended = session.ended_at
    previous_expires = session.expires_at
    if not already_live:
        await manager.stop_hosted_sessions_for_user(user_id)
        if session.visibility == ONLINE_COLLAB_VISIBILITY_ORGANIZATION and org_id is not None:
            live_count = await manager.count_live_org_sessions(org_id)
            if live_count >= MINDMATE_COLLAB_MAX_ORG_CONCURRENT_SESSIONS:
                return None, (
                    "Organization has reached the maximum of "
                    f"{MINDMATE_COLLAB_MAX_ORG_CONCURRENT_SESSIONS} "
                    "concurrent seminar rooms"
                )
        expires_at = compute_online_collab_expires_at(
            datetime.now(tz=UTC),
            reopen_duration(session.visibility, session.duration_preset),
        )
        await _set_ended_at(session.id, None, expires_at)
    else:
        expires_at = session.expires_at
        if expires_at is None or is_online_collab_expired(expires_at):
            expires_at = compute_online_collab_expires_at(
                datetime.now(tz=UTC),
                reopen_duration(session.visibility, session.duration_preset),
            )
            await _set_ended_at(session.id, None, expires_at)

    published = await manager.publish_live_room(
        code=session.code,
        session_id=session.id,
        owner_id=user_id,
        owner_name=owner_name,
        org_id=session.organization_id if session.organization_id is not None else org_id,
        title=session.title,
        visibility=session.visibility,
        expires_at=expires_at,
        bound_org_ids=bound_org_ids,
    )
    if not published:
        if not already_live and previous_ended is not None:
            await _set_ended_at(session.id, previous_ended, previous_expires)
        elif already_live and (previous_expires is None or is_online_collab_expired(previous_expires)):
            await _set_ended_at(session.id, None, previous_expires)
        return None, "Collaboration service unavailable"

    if session.dify_conversation_id:
        await manager.set_dify_conversation_id(session.id, session.dify_conversation_id)
    await record_collab_member(session.id, user_id)
    return _room_payload(session, expires_at), None
