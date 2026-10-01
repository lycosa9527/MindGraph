"""
Per-person read cursors for a MindMate seminar.

A cursor is the newest line that person has seen. Later lines in the same
room always have a higher id, so one number covers every line up to it.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import User
from models.domain.mindmate_collab import MindmateCollabMessage, MindmateCollabReadCursor
from services.features.mindmate_collab.message_history import display_name_for_user
from services.utils.typing_helpers import result_rowcount


def read_cursor_is_newer(current: Optional[int], incoming: int) -> bool:
    """True when ``incoming`` should replace this person's saved cursor."""
    if isinstance(incoming, bool) or not isinstance(incoming, int) or incoming <= 0:
        return False
    if current is None:
        return True
    return incoming > current


def serialize_read_cursor(
    user_id: int,
    username: Optional[str],
    last_read_message_id: int,
    read_at: datetime,
) -> Dict[str, Any]:
    """JSON shape shared by the join snapshot and live read frames."""
    payload: Dict[str, Any] = {
        "user_id": user_id,
        "last_read_message_id": last_read_message_id,
        "read_at": read_at.isoformat(),
    }
    if username:
        payload["username"] = username
    return payload


async def list_read_cursors(db: AsyncSession, session_id: str) -> List[Dict[str, Any]]:
    """Everyone's read cursor in one room, oldest read first."""
    result = await db.execute(
        select(MindmateCollabReadCursor, User.name, User.phone, User.email)
        .join(User, User.id == MindmateCollabReadCursor.user_id, isouter=True)
        .where(MindmateCollabReadCursor.session_id == session_id)
        .order_by(MindmateCollabReadCursor.read_at.asc()),
    )
    cursors: List[Dict[str, Any]] = []
    for cursor, name, phone, email in result.all():
        cursors.append(
            serialize_read_cursor(
                int(cursor.user_id),
                display_name_for_user(name, phone, email, cursor.user_id),
                int(cursor.last_read_message_id),
                cursor.read_at,
            ),
        )
    return cursors


async def advance_read_cursor(
    db: AsyncSession,
    session_id: str,
    user_id: int,
    message_id: int,
    username: Optional[str],
) -> Optional[Dict[str, Any]]:
    """Move this person's cursor forward. Returns the broadcast payload when it moved."""
    if not read_cursor_is_newer(None, message_id):
        return None
    owns_line = await db.execute(
        select(MindmateCollabMessage.id).where(
            MindmateCollabMessage.session_id == session_id,
            MindmateCollabMessage.id == message_id,
        ),
    )
    if owns_line.scalar_one_or_none() is None:
        return None
    read_at = datetime.now(tz=UTC)
    stmt = pg_insert(MindmateCollabReadCursor).values(
        session_id=session_id,
        user_id=user_id,
        last_read_message_id=message_id,
        read_at=read_at,
    )
    excluded = stmt.excluded
    stmt = stmt.on_conflict_do_update(
        index_elements=["session_id", "user_id"],
        set_={
            "last_read_message_id": excluded.last_read_message_id,
            "read_at": excluded.read_at,
        },
        where=MindmateCollabReadCursor.last_read_message_id < excluded.last_read_message_id,
    )
    result = await db.execute(stmt)
    await db.commit()
    if result_rowcount(result) == 0:
        return None
    return serialize_read_cursor(user_id, username, message_id, read_at)
