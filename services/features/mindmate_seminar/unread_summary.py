"""Unread lines in live MindMate seminars for one person."""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.mindmate_seminar import MindmateSeminarMessage, MindmateSeminarReadCursor
from services.features.mindmate_seminar.manager_access import get_mindmate_seminar_manager
from utils.db.session_open import user_rls_session


def message_is_unread(
    role: str,
    sender_user_id: Optional[int],
    viewer_id: int,
    message_id: int,
    cursor: Optional[int],
) -> bool:
    """True when this line is newer than the cursor and was not sent by the viewer."""
    if message_id <= (cursor or 0):
        return False
    return not (role == "user" and sender_user_id == viewer_id)


def rooms_from_counts(
    sessions: list[dict[str, Any]],
    counts: dict[str, tuple[int, int]],
) -> dict[str, Any]:
    """Keep live rooms that have unread lines, newest activity first."""
    rooms: list[dict[str, Any]] = []
    for session in sessions:
        session_id = str(session.get("session_id") or "")
        found = counts.get(session_id)
        if found is None:
            continue
        unread_count, latest_message_id = found
        if unread_count <= 0:
            continue
        rooms.append(
            {
                "session_id": session_id,
                "code": session.get("code") or "",
                "title": session.get("title") or "",
                "unread_count": unread_count,
                "latest_message_id": latest_message_id,
            }
        )
    rooms.sort(key=lambda room: int(room["latest_message_id"]), reverse=True)
    total = sum(int(room["unread_count"]) for room in rooms)
    return {"unread_count": total, "rooms": rooms}


async def _count_unread(db: AsyncSession, user_id: int, session_ids: list[str]) -> dict[str, tuple[int, int]]:
    if not session_ids:
        return {}
    newer_than_cursor = MindmateSeminarMessage.id > func.coalesce(MindmateSeminarReadCursor.last_read_message_id, 0)
    from_someone_else = ~and_(
        MindmateSeminarMessage.role == "user",
        MindmateSeminarMessage.sender_user_id == user_id,
    )
    unread_line = and_(newer_than_cursor, from_someone_else)
    result = await db.execute(
        select(
            MindmateSeminarMessage.session_id,
            func.max(MindmateSeminarMessage.id),
            func.count(case((unread_line, MindmateSeminarMessage.id))),
        )
        .outerjoin(
            MindmateSeminarReadCursor,
            and_(
                MindmateSeminarReadCursor.session_id == MindmateSeminarMessage.session_id,
                MindmateSeminarReadCursor.user_id == user_id,
            ),
        )
        .where(MindmateSeminarMessage.session_id.in_(session_ids))
        .group_by(MindmateSeminarMessage.session_id)
    )
    counts: dict[str, tuple[int, int]] = {}
    for session_id, latest_id, unread_count in result.all():
        counts[str(session_id)] = (int(unread_count or 0), int(latest_id or 0))
    return counts


async def summarize_live_unread(user_id: int) -> dict[str, Any]:
    """Unread summary for seminars this user hosts or has accepted."""
    sessions = await get_mindmate_seminar_manager().list_accessible_live_sessions(user_id)
    session_ids = [str(session["session_id"]) for session in sessions if session.get("session_id")]
    async with user_rls_session(user_id) as db:
        counts = await _count_unread(db, user_id, session_ids)
    return rooms_from_counts(sessions, counts)
