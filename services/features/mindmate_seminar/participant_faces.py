"""
Display rows for people currently in a MindMate seminar.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import select

from models.domain.auth import User
from utils.db.session_open import system_rls_session


def participant_face_payload(
    user_id: int,
    name: Optional[str],
    avatar: Optional[str],
) -> Dict[str, Any]:
    """One header avatar: id, display name, and stored emoji."""
    label = (name or "").strip() or f"User {user_id}"
    raw_avatar = (avatar or "").strip()
    return {
        "user_id": int(user_id),
        "name": label,
        "avatar": raw_avatar or None,
    }


def _unique_user_ids(user_ids: Sequence[int]) -> List[int]:
    unique: List[int] = []
    seen: set[int] = set()
    for raw in user_ids:
        try:
            user_id = int(raw)
        except (TypeError, ValueError):
            continue
        if user_id <= 0 or user_id in seen:
            continue
        seen.add(user_id)
        unique.append(user_id)
    return unique


async def load_participant_faces(user_ids: Sequence[int]) -> List[Dict[str, Any]]:
    """Load name and avatar for seminar participants, including other schools."""
    unique = _unique_user_ids(user_ids)
    if not unique:
        return []
    async with system_rls_session() as db:
        rows = (await db.execute(select(User.id, User.name, User.avatar).where(User.id.in_(unique)))).all()
    by_id = {int(row.id): row for row in rows}
    faces: List[Dict[str, Any]] = []
    for user_id in unique:
        row = by_id.get(user_id)
        if row is None:
            continue
        faces.append(participant_face_payload(user_id, row.name, row.avatar))
    return faces
