"""
Persist and load MindMate collab room message history.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import User
from models.domain.mindmate_collab import MindmateCollabMessage
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


async def fetch_session_message_history(
    db: AsyncSession,
    session_id: str,
    limit: int | None = None,
) -> List[Dict[str, Any]]:
    """Return recent chat rows oldest-first with sender display names."""
    cap = limit or MINDMATE_COLLAB_SNAPSHOT_MESSAGE_LIMIT
    result = await db.execute(
        select(MindmateCollabMessage, User.name, User.phone, User.email)
        .join(User, User.id == MindmateCollabMessage.sender_user_id, isouter=True)
        .where(MindmateCollabMessage.session_id == session_id)
        .order_by(MindmateCollabMessage.id.desc())
        .limit(cap),
    )
    rows = list(reversed(result.all()))
    return [
        serialize_message_row(message, owner_name, owner_phone, owner_email)
        for message, owner_name, owner_phone, owner_email in rows
    ]


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
