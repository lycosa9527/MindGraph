"""Shared group highlights (精华) for one seminar room.

Rows live in Postgres so every participant sees the same list after login.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import User
from models.domain.mindmate_seminar import MindmateSeminarHighlight, MindmateSeminarSession
from services.features.mindmate_seminar.group_members import (
    list_group_member_roles,
    user_observes_seminar,
)
from services.features.mindmate_seminar.seminar_roles import resolve_seminar_leader_id
from services.features.mindmate_seminar.ws_broadcast import broadcast_to_all
from utils.db.session_open import system_rls_session

MAX_HIGHLIGHTS = 200
MAX_HIGHLIGHT_TEXT = 65536
MAX_NAME = 80


@dataclass(frozen=True)
class SeminarHighlightDraft:
    """One highlight a participant wants to pin."""

    text: str
    author_name: str
    created_by_name: str
    message_id: Optional[int]
    message_at: Optional[datetime]


def parse_highlight_instant(raw: str | None) -> Optional[datetime]:
    """Parse an ISO timestamp from the seminar client."""
    if not raw or not raw.strip():
        return None
    try:
        parsed = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def highlight_payload(row: MindmateSeminarHighlight) -> dict[str, object]:
    """JSON body shared by REST and the seminar websocket."""
    return {
        "id": row.id,
        "text": row.text,
        "author_name": row.author_name,
        "message_id": row.message_id,
        "created_at": row.created_at.isoformat(),
        "created_by_user_id": row.created_by_user_id,
        "created_by_name": row.created_by_name,
        "message_at": row.message_at.isoformat() if row.message_at else None,
    }


def _clip_name(raw: str) -> str:
    return raw.strip()[:MAX_NAME]


def _clip_text(raw: str) -> str:
    return raw.strip()[:MAX_HIGHLIGHT_TEXT]


async def user_may_delete_highlight(
    session: MindmateSeminarSession,
    user_id: int,
    created_by_user_id: int,
) -> bool:
    """Creators can remove their own pin; the seminar leader can remove any."""
    if int(created_by_user_id) == int(user_id):
        return True
    roles = await list_group_member_roles(session.id)
    return resolve_seminar_leader_id(roles, int(session.owner_user_id)) == int(user_id)


async def list_seminar_highlights(session_id: str) -> list[dict[str, object]]:
    """Newest highlights first."""
    async with system_rls_session() as db:
        result = await db.execute(
            select(MindmateSeminarHighlight)
            .where(MindmateSeminarHighlight.session_id == session_id)
            .order_by(MindmateSeminarHighlight.created_at.desc())
        )
        return [highlight_payload(row) for row in result.scalars().all()]


async def create_seminar_highlight(
    session: MindmateSeminarSession,
    user: User,
    draft: SeminarHighlightDraft,
) -> dict[str, object]:
    """Persist one highlight and tell everyone in the room."""
    text = _clip_text(draft.text)
    if not text:
        raise ValueError("empty")
    if await user_observes_seminar(session.id, int(user.id)):
        raise ValueError("observer_readonly")
    message_id = int(draft.message_id) if draft.message_id else None
    row = MindmateSeminarHighlight(
        id=str(uuid4()),
        session_id=session.id,
        created_by_user_id=int(user.id),
        created_by_name=_clip_name(draft.created_by_name or user.name or ""),
        author_name=_clip_name(draft.author_name) or _clip_name(user.name or ""),
        text=text,
        message_id=message_id,
        message_at=draft.message_at,
        created_at=datetime.now(UTC),
    )
    async with system_rls_session() as db:
        count = await db.scalar(
            select(func.count(MindmateSeminarHighlight.id)).where(MindmateSeminarHighlight.session_id == session.id)
        )
        if int(count or 0) >= MAX_HIGHLIGHTS:
            raise ValueError("highlight_limit")
        db.add(row)
        try:
            await db.flush()
            payload = highlight_payload(row)
            await db.commit()
        except IntegrityError:
            await db.rollback()
            existing = await _existing_message_highlight(db, session.id, int(user.id), message_id)
            if existing is None:
                raise ValueError("duplicate") from None
            payload = highlight_payload(existing)
    await broadcast_to_all(
        session.code,
        {
            "type": "seminar_highlight",
            "action": "set",
            "highlight": payload,
            "actor_user_id": int(user.id),
            "actor_name": user.name or "",
        },
    )
    return payload


async def _existing_message_highlight(
    db: AsyncSession,
    session_id: str,
    user_id: int,
    message_id: Optional[int],
) -> Optional[MindmateSeminarHighlight]:
    if message_id is None:
        return None
    result = await db.execute(
        select(MindmateSeminarHighlight).where(
            MindmateSeminarHighlight.session_id == session_id,
            MindmateSeminarHighlight.message_id == message_id,
            MindmateSeminarHighlight.created_by_user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def delete_seminar_highlight(
    session: MindmateSeminarSession,
    user: User,
    highlight_id: str,
) -> dict[str, object]:
    """Remove a highlight the caller owns, or any highlight if they lead the room."""
    if await user_observes_seminar(session.id, int(user.id)):
        raise ValueError("observer_readonly")
    async with system_rls_session() as db:
        row = await db.get(MindmateSeminarHighlight, highlight_id)
        if row is None or row.session_id != session.id:
            raise ValueError("room_not_found")
        if not await user_may_delete_highlight(session, int(user.id), int(row.created_by_user_id)):
            raise ValueError("forbidden")
        payload = highlight_payload(row)
        await db.delete(row)
        await db.commit()
    await broadcast_to_all(
        session.code,
        {
            "type": "seminar_highlight",
            "action": "cancel",
            "highlight": payload,
            "actor_user_id": int(user.id),
            "actor_name": user.name or "",
        },
    )
    return payload


__all__ = [
    "MAX_HIGHLIGHTS",
    "MAX_HIGHLIGHT_TEXT",
    "SeminarHighlightDraft",
    "create_seminar_highlight",
    "delete_seminar_highlight",
    "highlight_payload",
    "list_seminar_highlights",
    "parse_highlight_instant",
    "user_may_delete_highlight",
]
