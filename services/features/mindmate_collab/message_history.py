"""
Persist and load MindMate collab room message history.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Dict, List, NamedTuple, Optional, Sequence, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import User
from models.domain.mindmate_collab import MindmateCollabMessage, MindmateCollabSession
from services.features.mindmate_collab.config import (
    MINDMATE_COLLAB_MAX_CHAT_CONTENT_CHARS,
    MINDMATE_COLLAB_SNAPSHOT_MESSAGE_LIMIT,
)

_VALID_SEED_ROLES = frozenset({"user", "assistant"})


def display_name_for_user(
    name: Optional[str],
    phone: Optional[str],
    email: Optional[str],
    user_id: Optional[int],
) -> Optional[str]:
    """Resolve a human-readable sender label for chat history."""
    for candidate in (name, phone, email):
        if candidate and str(candidate).strip():
            return str(candidate).strip()
    if user_id is not None:
        return str(user_id)
    return None


def serialize_message_row(
    row: MindmateCollabMessage,
    owner_name: Optional[str],
    owner_phone: Optional[str],
    owner_email: Optional[str],
) -> Dict[str, Any]:
    """Build a JSON-serializable chat row for REST/WS snapshot frames."""
    username = None
    if row.role == "user":
        username = display_name_for_user(owner_name, owner_phone, owner_email, row.sender_user_id)
    return {
        "id": row.id,
        "role": row.role,
        "content": row.content,
        "sender_user_id": row.sender_user_id,
        "username": username,
        "created_at": row.created_at.isoformat(),
    }


class PersistedCollabMessage(NamedTuple):
    """Saved seminar line, the previous line id in the same room, and its stamp."""

    id: int
    prev_id: Optional[int]
    created_at: str


class CollabHistoryPage(NamedTuple):
    """One page of seminar history, plus whether another page exists in that direction."""

    messages: List[Dict[str, Any]]
    has_more: bool


def page_history_probe(
    rows: Sequence[Any],
    cap: int,
    *,
    newest_first: bool,
) -> Tuple[List[Any], bool]:
    """Keep ``cap`` rows from a probe that may include one extra row."""
    has_more = len(rows) > cap
    kept = list(rows[:cap])
    if newest_first:
        kept.reverse()
    return kept, has_more


async def fetch_session_message_page(
    db: AsyncSession,
    session_id: str,
    limit: int | None = None,
    after_id: int | None = None,
    before_id: int | None = None,
) -> CollabHistoryPage:
    """
    Return one page of chat rows, oldest-first.

    No cursor returns the newest page. ``after_id`` returns newer rows.
    ``before_id`` returns older rows. ``has_more`` is the next page in that direction.
    """
    cap = limit or MINDMATE_COLLAB_SNAPSHOT_MESSAGE_LIMIT
    newest_first = after_id is None
    stmt = (
        select(MindmateCollabMessage, User.name, User.phone, User.email)
        .join(User, User.id == MindmateCollabMessage.sender_user_id, isouter=True)
        .where(MindmateCollabMessage.session_id == session_id)
    )
    if after_id is not None:
        stmt = stmt.where(MindmateCollabMessage.id > after_id).order_by(MindmateCollabMessage.id.asc())
    elif before_id is not None:
        stmt = stmt.where(MindmateCollabMessage.id < before_id).order_by(MindmateCollabMessage.id.desc())
    else:
        stmt = stmt.order_by(MindmateCollabMessage.id.desc())
    result = await db.execute(stmt.limit(cap + 1))
    fetched, has_more = page_history_probe(list(result.all()), cap, newest_first=newest_first)
    messages = [
        serialize_message_row(message, owner_name, owner_phone, owner_email)
        for message, owner_name, owner_phone, owner_email in fetched
    ]
    return CollabHistoryPage(messages, has_more)


async def fetch_session_message_history(
    db: AsyncSession,
    session_id: str,
    limit: int | None = None,
    after_id: int | None = None,
    before_id: int | None = None,
) -> List[Dict[str, Any]]:
    """Return chat rows oldest-first. ``after_id`` keeps only newer rows."""
    page = await fetch_session_message_page(
        db,
        session_id,
        limit=limit,
        after_id=after_id,
        before_id=before_id,
    )
    return page.messages


async def insert_collab_message(
    db: AsyncSession,
    session_id: str,
    *,
    role: str,
    content: str,
    sender_user_id: Optional[int],
) -> PersistedCollabMessage:
    """Insert one room line. The session row lock keeps prev_id a single chain."""
    await db.execute(
        select(MindmateCollabSession.id).where(MindmateCollabSession.id == session_id).with_for_update(),
    )
    previous = await db.execute(
        select(MindmateCollabMessage.id)
        .where(MindmateCollabMessage.session_id == session_id)
        .order_by(MindmateCollabMessage.id.desc())
        .limit(1),
    )
    raw_prev = previous.scalar_one_or_none()
    prev_id = raw_prev if isinstance(raw_prev, int) and not isinstance(raw_prev, bool) else None
    msg = MindmateCollabMessage(
        session_id=session_id,
        role=role,
        content=content,
        sender_user_id=sender_user_id,
        created_at=datetime.now(tz=UTC),
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)
    return PersistedCollabMessage(
        id=int(msg.id),
        prev_id=prev_id,
        created_at=msg.created_at.isoformat(),
    )


def normalize_seed_messages(
    raw_messages: Sequence[Dict[str, Any]],
    owner_user_id: int,
) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
    """Validate and normalize seed messages from the start-room API."""
    if not raw_messages:
        return [], None
    if len(raw_messages) > MINDMATE_COLLAB_SNAPSHOT_MESSAGE_LIMIT:
        return None, "Too many seed messages"

    normalized: List[Dict[str, Any]] = []
    for raw in raw_messages:
        role = str(raw.get("role") or "").strip().lower()
        content = str(raw.get("content") or "").strip()
        if role not in _VALID_SEED_ROLES:
            return None, "Invalid seed message role"
        if not content:
            continue
        if len(content) > MINDMATE_COLLAB_MAX_CHAT_CONTENT_CHARS:
            return None, "Seed message too long"
        sender_user_id: Optional[int]
        if role == "assistant":
            sender_user_id = None
        else:
            sender_user_id = owner_user_id
        normalized.append(
            {
                "role": role,
                "content": content,
                "sender_user_id": sender_user_id,
            },
        )
    return normalized, None


def history_row_ids(rows: Sequence[Dict[str, Any]]) -> set[int]:
    """Ids already included in a join snapshot."""
    found: set[int] = set()
    for row in rows:
        raw_id = row.get("id")
        if isinstance(raw_id, int) and not isinstance(raw_id, bool):
            found.add(raw_id)
    return found


def catchup_frames(
    baseline_ids: set[int],
    fresh_rows: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Frames for rows committed after the join snapshot was read.

    Fan-out is ignored until that snapshot is queued, so a message saved in
    between is neither in the snapshot nor in the live stream.
    """
    previous_by_id: Dict[int, Optional[int]] = {}
    previous_id: Optional[int] = None
    for row in fresh_rows:
        raw_id = row.get("id")
        if not isinstance(raw_id, int) or isinstance(raw_id, bool):
            continue
        previous_by_id[raw_id] = previous_id
        previous_id = raw_id
    frames: List[Dict[str, Any]] = []
    for row in fresh_rows:
        raw_id = row.get("id")
        if not isinstance(raw_id, int) or isinstance(raw_id, bool) or raw_id in baseline_ids:
            continue
        content = row.get("content")
        if not isinstance(content, str):
            continue
        role = row.get("role")
        prev_id = previous_by_id.get(raw_id)
        created_at = row.get("created_at") if isinstance(row.get("created_at"), str) else None
        if role == "user":
            frame: Dict[str, Any] = {
                "type": "user_message",
                "id": raw_id,
                "prev_id": prev_id,
                "content": content,
                "sender_user_id": row.get("sender_user_id"),
                "username": row.get("username"),
            }
            if created_at:
                frame["created_at"] = created_at
            frames.append(frame)
        elif role == "assistant":
            frame = {
                "type": "ai_message_end",
                "id": raw_id,
                "prev_id": prev_id,
                "content": content,
            }
            if created_at:
                frame["created_at"] = created_at
            frames.append(frame)
    return frames


async def persist_seed_messages(
    db: AsyncSession,
    session_id: str,
    messages: Sequence[Dict[str, Any]],
) -> int:
    """Insert seed messages for a newly created session; return count saved."""
    if not messages:
        return 0
    now = datetime.now(tz=UTC)
    for item in messages:
        db.add(
            MindmateCollabMessage(
                session_id=session_id,
                role=str(item["role"]),
                content=str(item["content"]),
                sender_user_id=item.get("sender_user_id"),
                created_at=now,
            ),
        )
    await db.commit()
    return len(messages)
