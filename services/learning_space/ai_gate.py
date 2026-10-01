"""Enforce per-assignment AI permissions for student accounts.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging

from fastapi import HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import User
from models.domain.learning_space import LearningAssignment
from services.learning_space.access import (
    assert_assignment_visible_to_learner,
    require_class_learner,
)
from services.learning_space.passwords import ai_permission_allowed
from utils.auth.roles import is_student

logger = logging.getLogger(__name__)


def resolve_assignment_id(request: Request) -> int | None:
    """Read assignment id from header or query."""
    raw = request.headers.get("X-MG-Assignment-Id") or request.query_params.get("assignment_id")
    if raw is None or str(raw).strip() == "":
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


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
