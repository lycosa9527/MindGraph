"""
Activity tracking side effects for one-sentence panel turns.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any, Dict, Optional

from sqlalchemy import select

from models.domain.auth import User
from models.domain.user_activity_log import UserActivityLog
from services.admin.user_usage_activity import (
    clip_activity_preview,
    schedule_user_usage_activity,
)
from services.redis.redis_activity_tracker import get_activity_tracker
from services.utils.error_types import BACKGROUND_INFRA_ERRORS
from utils.auth.roles import is_teacher
from utils.db.session_open import system_rls_session

logger = logging.getLogger(__name__)

_TEACHER_LOG_TYPES = frozenset({"one_sentence_generate", "one_sentence_edit"})


def _resolve_usage_action(turn: Dict[str, Any]) -> Optional[str]:
    role = str(turn.get("role") or "")
    phase = str(turn.get("phase") or "")
    if role == "user" and phase == "create":
        return "one_sentence_generate"
    if role == "kitty" and turn.get("user_text"):
        return "one_sentence_edit"
    if role == "user" and phase == "edit":
        return "one_sentence_edit"
    return None


def _resolve_teacher_activity_type(turn: Dict[str, Any]) -> Optional[str]:
    role = str(turn.get("role") or "")
    phase = str(turn.get("phase") or "")
    if role == "user" and phase == "create":
        return "one_sentence_generate"
    if role == "user" and phase == "edit":
        return "one_sentence_edit"
    if role == "kitty" and str(turn.get("outcome") or "") == "executed":
        return "one_sentence_edit"
    return None


def _diagram_id_from_scope(scope: str) -> Optional[str]:
    cleaned = str(scope or "").strip()
    if len(cleaned) == 36 and cleaned.count("-") == 4:
        return cleaned
    return None


async def _record_redis_activity(
    *,
    user_id: int,
    turn: Dict[str, Any],
    scope: str,
    session_id: Optional[str] = None,
) -> None:
    tracker = get_activity_tracker()
    await tracker.record_activity(
        user_id=user_id,
        user_phone="",
        activity_type="one_sentence_turn",
        details={
            "session_id": session_id or turn.get("session_id"),
            "scope": scope,
            "role": turn.get("role"),
            "phase": turn.get("phase"),
            "source": turn.get("source"),
            "action": turn.get("action"),
            "outcome": turn.get("outcome"),
            "diagram_type": turn.get("diagram_type"),
            "request_id": turn.get("request_id"),
            "command_detail": turn.get("command_detail"),
        },
    )


async def _log_teacher_activity(user_id: int, activity_type: str) -> None:
    if activity_type not in _TEACHER_LOG_TYPES:
        return
    try:
        async with system_rls_session() as session:
            result = await session.execute(select(User).where(User.id == int(user_id)).limit(1))
            user = result.scalar_one_or_none()
            if user is None or not is_teacher(user):
                return
            session.add(
                UserActivityLog(
                    user_id=int(user_id),
                    activity_type=activity_type,
                    created_at=datetime.now(UTC),
                )
            )
            await session.commit()
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.debug("[OneSentenceActivity] teacher log failed user=%s: %s", user_id, exc)


async def record_one_sentence_turn_activity(
    *,
    user_id: int,
    organization_id: Optional[int],
    scope: str,
    turn: Dict[str, Any],
    session_id: Optional[str] = None,
) -> None:
    """Persist admin timeline + teacher log + Redis activity for one turn."""
    if user_id <= 0:
        return

    track_session_id = session_id or str(turn.get("session_id") or "").strip() or None

    try:
        await _record_redis_activity(
            user_id=user_id,
            turn=turn,
            scope=scope,
            session_id=track_session_id,
        )
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.debug("[OneSentenceActivity] redis track failed user=%s: %s", user_id, exc)

    usage_action = _resolve_usage_action(turn)
    if usage_action is not None:
        role = str(turn.get("role") or "")
        content = clip_activity_preview(str(turn.get("content") or ""))
        user_text = clip_activity_preview(str(turn.get("user_text") or ""))
        prompt_preview = user_text if role == "kitty" else content
        reply_preview = content if role == "kitty" else None
        outcome = str(turn.get("outcome") or "")
        success = outcome not in ("failed", "low_confidence")
        node_action = str(turn.get("action") or "").strip() or None
        request_id = str(turn.get("request_id") or "").strip() or None
        # Title carries the node action name for admin timeline drill-down.
        title = clip_activity_preview(node_action, max_len=64) if node_action else None
        conversation_id = track_session_id or scope
        if request_id and conversation_id:
            conversation_id = f"{conversation_id}:{request_id}"
        elif request_id:
            conversation_id = request_id
        schedule_user_usage_activity(
            user_id=user_id,
            organization_id=organization_id,
            source="mindgraph",
            action=usage_action,
            title=title,
            prompt_preview=prompt_preview,
            reply_preview=reply_preview,
            diagram_type=str(turn.get("diagram_type") or "") or None,
            diagram_id=_diagram_id_from_scope(scope),
            conversation_id=conversation_id,
            success=success,
        )

    teacher_type = _resolve_teacher_activity_type(turn)
    if teacher_type is not None:
        await _log_teacher_activity(user_id, teacher_type)


def schedule_one_sentence_turn_activity(
    *,
    user_id: int,
    organization_id: Optional[int],
    scope: str,
    turn: Dict[str, Any],
    session_id: Optional[str] = None,
) -> None:
    """Fire-and-forget activity tracking for a stored turn."""
    asyncio.create_task(
        record_one_sentence_turn_activity(
            user_id=user_id,
            organization_id=organization_id,
            scope=scope,
            turn=turn,
            session_id=session_id,
        )
    )
