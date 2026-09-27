"""
Save a finished MindMate seminar into the owner's library.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import User
from models.domain.mindmate_collab import MindmateCollabMessage, MindmateCollabSession
from services.features.mindmate_collab.config import (
    MINDMATE_COLLAB_LIBRARY_LIST_LIMIT,
    MINDMATE_COLLAB_LIBRARY_MESSAGE_LIMIT,
)
from services.features.mindmate_collab.message_history import serialize_message_row
from utils.db.session_open import system_rls_session, user_rls_session


def finished_seminar_save_block_reason(
    *,
    ended_at: Optional[datetime],
    owner_user_id: int,
    actor_user_id: int,
) -> Optional[str]:
    """Return why this actor cannot save the seminar, or None when save is allowed."""
    if owner_user_id != actor_user_id:
        return "not_owner"
    if ended_at is None:
        return "still_live"
    return None


def _iso_timestamp(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    text = value.isoformat()
    if value.tzinfo is None:
        return f"{text}Z"
    return text


def saved_seminar_summary(session: MindmateCollabSession) -> Dict[str, Any]:
    """JSON row for the owner's saved-seminar list and transcript header."""
    return {
        "session_id": session.id,
        "title": session.title,
        "visibility": session.visibility,
        "ended_at": _iso_timestamp(session.ended_at),
        "library_saved_at": _iso_timestamp(session.library_saved_at),
    }


async def save_finished_seminar_for_owner(
    session_id: str,
    owner_user_id: int,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Mark an ended seminar as saved for its owner. Idempotent."""
    async with user_rls_session(owner_user_id) as db:
        session = (
            await db.execute(
                select(MindmateCollabSession).where(MindmateCollabSession.id == session_id),
            )
        ).scalar_one_or_none()
        if session is None:
            return None, "not_found"
        reason = finished_seminar_save_block_reason(
            ended_at=session.ended_at,
            owner_user_id=session.owner_user_id,
            actor_user_id=owner_user_id,
        )
        if reason == "not_owner":
            return None, "not_found"
        if reason:
            return None, reason
        if session.library_saved_at is None:
            session.library_saved_at = datetime.now(tz=UTC)
            await db.commit()
            await db.refresh(session)
        return saved_seminar_summary(session), None


async def list_saved_seminars(owner_user_id: int) -> List[Dict[str, Any]]:
    """Return the owner's saved finished seminars, newest save first."""
    async with user_rls_session(owner_user_id) as db:
        rows = (
            (
                await db.execute(
                    select(MindmateCollabSession)
                    .where(
                        MindmateCollabSession.owner_user_id == owner_user_id,
                        MindmateCollabSession.library_saved_at.is_not(None),
                    )
                    .order_by(MindmateCollabSession.library_saved_at.desc())
                    .limit(MINDMATE_COLLAB_LIBRARY_LIST_LIMIT),
                )
            )
            .scalars()
            .all()
        )
    return [saved_seminar_summary(row) for row in rows]


async def _load_transcript(db: AsyncSession, session_id: str) -> Tuple[List[Dict[str, Any]], bool]:
    limit = MINDMATE_COLLAB_LIBRARY_MESSAGE_LIMIT
    count = int(
        await db.scalar(
            select(func.count())
            .select_from(MindmateCollabMessage)
            .where(MindmateCollabMessage.session_id == session_id),
        )
        or 0
    )
    truncated = count > limit
    stmt = (
        select(MindmateCollabMessage, User.name, User.phone, User.email)
        .join(User, User.id == MindmateCollabMessage.sender_user_id, isouter=True)
        .where(MindmateCollabMessage.session_id == session_id)
        .order_by(MindmateCollabMessage.id.asc())
    )
    if truncated:
        stmt = stmt.offset(count - limit)
    rows = (await db.execute(stmt)).all()
    messages = [
        serialize_message_row(message, owner_name, owner_phone, owner_email)
        for message, owner_name, owner_phone, owner_email in rows
    ]
    return messages, truncated


async def load_saved_seminar(
    session_id: str,
    owner_user_id: int,
) -> Optional[Dict[str, Any]]:
    """Return one saved seminar and its full transcript for the owner."""
    async with user_rls_session(owner_user_id) as db:
        session = (
            await db.execute(
                select(MindmateCollabSession).where(MindmateCollabSession.id == session_id),
            )
        ).scalar_one_or_none()
        if session is None or session.owner_user_id != owner_user_id:
            return None
        if session.library_saved_at is None:
            return None
        summary = saved_seminar_summary(session)
    async with system_rls_session() as db:
        messages, truncated = await _load_transcript(db, session_id)
    return {"session": summary, "messages": messages, "truncated": truncated}
