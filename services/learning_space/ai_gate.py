"""Enforce per-assignment AI permissions for student accounts.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException, Request, WebSocket, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import User
from models.domain.learning_space import LearningAssignment
from services.kitty.routing.one_sentence_edit_helpers import is_one_sentence_edit_mode
from services.kitty.session.runtime_state import voice_sessions
from services.learning_space.access import (
    assert_assignment_visible_to_learner,
    require_class_learner,
)
from services.learning_space.passwords import ai_permission_allowed
from utils.auth.roles import is_student
from utils.db.session_open import user_rls_session

logger = logging.getLogger(__name__)


def _parse_assignment_id(raw: Any) -> int | None:
    if raw is None or str(raw).strip() == "":
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def resolve_assignment_id(request: Request) -> int | None:
    """Read assignment id from header or query."""
    raw = request.headers.get("X-MG-Assignment-Id") or request.query_params.get("assignment_id")
    return _parse_assignment_id(raw)


def resolve_assignment_id_from_websocket(websocket: WebSocket) -> int | None:
    """Read homework assignment id from Kitty / voice WS query string."""
    return _parse_assignment_id(websocket.query_params.get("assignment_id"))


def store_learning_assignment_on_voice_session(
    voice_session_id: str,
    assignment_id: int | None,
) -> None:
    """Attach Learning Space homework context to a Kitty voice session."""
    session = voice_sessions.get(voice_session_id)
    if isinstance(session, dict):
        session["learning_assignment_id"] = assignment_id


def voice_session_learning_assignment_id(voice_session_id: str) -> int | None:
    """Read the homework assignment id attached to a Kitty voice session."""
    session = voice_sessions.get(voice_session_id) or {}
    return _parse_assignment_id(session.get("learning_assignment_id"))


def resolve_kitty_voice_session_capability(
    voice_session_id: str,
    session_context: dict[str, Any] | None,
) -> str:
    """Map a Kitty one-sentence / canvas session to a Learning Space AI capability."""
    live = voice_sessions.get(voice_session_id) or {}
    ctx = session_context if isinstance(session_context, dict) else {}
    panel = str(live.get("active_panel") or "").strip()
    if panel == "one_sentence":
        if is_one_sentence_edit_mode(ctx, live if isinstance(live, dict) else None):
            return "conversational_edit"
        return "topic_generate"
    return "conversational_edit"


async def assert_student_ai_capability(
    db: AsyncSession,
    user: User,
    request: Request,
    capability: str,
) -> None:
    """
    For students, require an assignment context that grants ``capability``.

    Non-students are no-ops.
    """
    await assert_student_ai_capability_for_assignment(
        db,
        user,
        resolve_assignment_id(request),
        capability,
    )


async def assert_student_ai_capability_for_assignment(
    db: AsyncSession,
    user: User,
    assignment_id: int | None,
    capability: str,
) -> None:
    """Same as ``assert_student_ai_capability`` with an explicit assignment id."""
    if assignment_id is None:
        if is_student(user):
            logger.warning(
                "[LearningSpace] AI denied user=%s capability=%s reason=missing_assignment",
                user.id,
                capability,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Assignment context required for student AI",
            )
        return
    result = await db.execute(select(LearningAssignment).where(LearningAssignment.id == assignment_id))
    assignment = result.scalar_one_or_none()
    if assignment is None:
        logger.warning(
            "[LearningSpace] AI denied user=%s assignment=%s capability=%s reason=not_found",
            user.id,
            assignment_id,
            capability,
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")
    assert_assignment_visible_to_learner(assignment)
    try:
        await require_class_learner(db, user, int(assignment.class_id))
    except HTTPException:
        logger.warning(
            "[LearningSpace] AI denied user=%s assignment=%s class=%s capability=%s reason=not_learner",
            user.id,
            assignment_id,
            assignment.class_id,
            capability,
        )
        raise
    perms = assignment.ai_permissions if isinstance(assignment.ai_permissions, dict) else {}
    if not ai_permission_allowed(perms, capability):
        logger.warning(
            "[LearningSpace] AI denied user=%s assignment=%s capability=%s reason=not_allowed",
            user.id,
            assignment_id,
            capability,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"AI capability '{capability}' not allowed for this assignment",
        )


async def assert_student_ai_for_voice_session(
    db: AsyncSession,
    voice_session_id: str,
    capability: str,
) -> None:
    """Enforce Learning Space AI permissions for student Kitty / voice sessions."""
    session = voice_sessions.get(voice_session_id) or {}
    user_id_raw = session.get("user_id")
    if user_id_raw is None:
        return
    try:
        user_id = int(user_id_raw)
    except (TypeError, ValueError):
        return
    user = await db.get(User, user_id)
    if user is None or not is_student(user):
        return
    assignment_id = voice_session_learning_assignment_id(voice_session_id)
    await assert_student_ai_capability_for_assignment(db, user, assignment_id, capability)


async def kitty_student_ai_denied_message(
    voice_session_id: str,
    session_context: dict[str, Any] | None,
) -> str | None:
    """Return a short denial message for Kitty turns, or None when allowed."""
    session = voice_sessions.get(voice_session_id) or {}
    user_id_raw = session.get("user_id")
    if user_id_raw is None:
        return None
    try:
        user_id = int(user_id_raw)
    except (TypeError, ValueError):
        return None

    capability = resolve_kitty_voice_session_capability(voice_session_id, session_context)
    try:
        async with user_rls_session(user_id) as db:
            user = await db.get(User, user_id)
            if user is None or not is_student(user):
                return None
            await assert_student_ai_for_voice_session(db, voice_session_id, capability)
    except HTTPException as exc:
        detail = str(exc.detail) if exc.detail else ""
        if "not allowed for this assignment" in detail:
            return "这次作业不允许使用该 AI 功能。"
        if "Assignment context required" in detail:
            return "请从学习空间打开作业后再使用 AI。"
        if detail:
            return detail[:240]
        return "这次作业不允许使用该 AI 功能。"
    return None
