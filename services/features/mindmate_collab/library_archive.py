"""
Save a finished MindMate seminar into the history of everyone who joined.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import User
from models.domain.mindmate_collab import (
    MindmateCollabMember,
    MindmateCollabMessage,
    MindmateCollabSession,
)
from services.features.mindmate_collab.config import (
    MINDMATE_COLLAB_LIBRARY_LIST_LIMIT,
    MINDMATE_COLLAB_LIBRARY_MESSAGE_LIMIT,
)
from services.features.mindmate_collab.message_history import serialize_message_row
from services.features.mindmate_collab.read_cursors import list_read_cursors
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


_TITLE_MAX_LENGTH = 200


def normalize_saved_seminar_title(raw: str) -> str:
    """Trim a seminar title. Empty means the caller must reject it."""
    return raw.strip()


def saved_seminar_title_error(raw: str) -> Optional[str]:
    """Return why a title cannot be stored, or None when it is usable."""
    title = normalize_saved_seminar_title(raw)
    if not title:
        return "empty_title"
    if len(title) > _TITLE_MAX_LENGTH:
        return "title_too_long"
    return None


def saved_seminar_edit_block_reason(
    *,
    owner_user_id: int,
    actor_user_id: int,
    library_saved_at: Optional[datetime],
    ended_at: Optional[datetime],
) -> Optional[str]:
    """Return why this actor cannot rename, pin, or delete the saved seminar."""
    if owner_user_id != actor_user_id or library_saved_at is None:
        return "not_found"
    if ended_at is None:
        return "still_live"
    return None


def viewer_may_open_saved_seminar(
    *,
    owner_user_id: int,
    viewer_user_id: int,
    library_saved_at: Optional[datetime],
    is_member: bool,
) -> bool:
    """True when this person may open the finished seminar transcript."""
    if library_saved_at is None:
        return False
    if viewer_user_id == owner_user_id:
        return True
    return is_member


def saved_seminar_summary(
    session: MindmateCollabSession,
    viewer_user_id: int,
) -> Dict[str, Any]:
    """JSON row for one person's saved-seminar list and transcript header."""
    owned = session.owner_user_id == viewer_user_id
    return {
        "session_id": session.id,
        "title": session.title,
        "visibility": session.visibility,
        "pinned": bool(session.library_pinned) if owned else False,
        "owned": owned,
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
        return saved_seminar_summary(session, owner_user_id), None


async def list_saved_seminars(user_id: int) -> List[Dict[str, Any]]:
    """Return finished seminars this person hosted or joined, newest save first.

    Uses a system session because a joiner is not the owner, and a network
    room is not visible to every joiner under the session row policy. The
    filter is the access check: owner, or a recorded member.
    """
    owner_pin = case(
        (
            and_(
                MindmateCollabSession.owner_user_id == user_id,
                MindmateCollabSession.library_pinned.is_(True),
            ),
            1,
        ),
        else_=0,
    )
    member_of = (
        select(MindmateCollabMember.session_id)
        .where(
            MindmateCollabMember.session_id == MindmateCollabSession.id,
            MindmateCollabMember.user_id == user_id,
        )
        .exists()
    )
    async with system_rls_session() as db:
        rows = (
            (
                await db.execute(
                    select(MindmateCollabSession)
                    .where(
                        MindmateCollabSession.library_saved_at.is_not(None),
                        or_(
                            MindmateCollabSession.owner_user_id == user_id,
                            member_of,
                        ),
                    )
                    .order_by(
                        owner_pin.desc(),
                        MindmateCollabSession.library_saved_at.desc(),
                    )
                    .limit(MINDMATE_COLLAB_LIBRARY_LIST_LIMIT),
                )
            )
            .scalars()
            .all()
        )
    return [saved_seminar_summary(row, user_id) for row in rows]


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


async def _viewer_is_member(db: AsyncSession, session_id: str, user_id: int) -> bool:
    found = await db.scalar(
        select(MindmateCollabMember.user_id).where(
            MindmateCollabMember.session_id == session_id,
            MindmateCollabMember.user_id == user_id,
        ),
    )
    return found is not None


async def load_saved_seminar(
    session_id: str,
    user_id: int,
) -> Optional[Dict[str, Any]]:
    """Return one saved seminar and its transcript for a host or a joiner."""
    async with system_rls_session() as db:
        session = (
            await db.execute(
                select(MindmateCollabSession).where(MindmateCollabSession.id == session_id),
            )
        ).scalar_one_or_none()
        if session is None:
            return None
        is_member = await _viewer_is_member(db, session_id, user_id)
        if not viewer_may_open_saved_seminar(
            owner_user_id=session.owner_user_id,
            viewer_user_id=user_id,
            library_saved_at=session.library_saved_at,
            is_member=is_member,
        ):
            return None
        summary = saved_seminar_summary(session, user_id)
        messages, truncated = await _load_transcript(db, session_id)
        read_cursors = await list_read_cursors(db, session_id)
    return {
        "session": summary,
        "messages": messages,
        "truncated": truncated,
        "read_cursors": read_cursors,
    }


async def _owned_saved_session(
    db: AsyncSession,
    session_id: str,
    owner_user_id: int,
) -> Tuple[Optional[MindmateCollabSession], Optional[str]]:
    session = (
        await db.execute(
            select(MindmateCollabSession).where(MindmateCollabSession.id == session_id),
        )
    ).scalar_one_or_none()
    if session is None:
        return None, "not_found"
    reason = saved_seminar_edit_block_reason(
        owner_user_id=session.owner_user_id,
        actor_user_id=owner_user_id,
        library_saved_at=session.library_saved_at,
        ended_at=session.ended_at,
    )
    if reason:
        return None, reason
    return session, None


async def update_saved_seminar(
    session_id: str,
    owner_user_id: int,
    *,
    title: Optional[str] = None,
    pinned: Optional[bool] = None,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Rename and/or pin a saved seminar. Returns the updated row, or an error code."""
    if title is None and pinned is None:
        return None, "empty_update"
    if title is not None:
        title_error = saved_seminar_title_error(title)
        if title_error:
            return None, title_error
        title = normalize_saved_seminar_title(title)
    async with user_rls_session(owner_user_id) as db:
        session, reason = await _owned_saved_session(db, session_id, owner_user_id)
        if reason or session is None:
            return None, reason or "not_found"
        if title is not None:
            session.title = title
        if pinned is not None:
            session.library_pinned = pinned
        await db.commit()
        await db.refresh(session)
        return saved_seminar_summary(session, owner_user_id), None


async def delete_saved_seminar(session_id: str, owner_user_id: int) -> Optional[str]:
    """Remove a saved seminar and its transcript. None means it was deleted."""
    async with user_rls_session(owner_user_id) as db:
        session, reason = await _owned_saved_session(db, session_id, owner_user_id)
        if reason or session is None:
            return reason or "not_found"
        await db.delete(session)
        await db.commit()
    return None
