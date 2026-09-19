"""Access helpers for Learning Space roles and ownership.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import config
from models.domain.auth import User
from models.domain.learning_space import (
    ASSIGNMENT_STATUS_DRAFT,
    CLASS_STATUS_ACTIVE,
    LearningAssignment,
    LearningClass,
    LearningPilotTeacher,
)
from services.learning_space.memberships import is_class_assistant, is_class_learner
from utils.auth.roles import is_student, is_superadmin


async def require_feature_enabled() -> None:
    """Raise 404 when Learning Space feature flag is off."""
    if not config.FEATURE_STUDENT_LEARNING_SPACE:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


async def get_enabled_pilot(
    db: AsyncSession,
    teacher_user_id: int,
) -> LearningPilotTeacher | None:
    """Return enabled pilot grant for teacher, if any."""
    result = await db.execute(
        select(LearningPilotTeacher).where(
            LearningPilotTeacher.teacher_user_id == teacher_user_id,
            LearningPilotTeacher.enabled.is_(True),
        )
    )
    return result.scalar_one_or_none()


async def require_pilot_teacher(db: AsyncSession, user: User) -> LearningPilotTeacher:
    """Ensure current user is an enabled pilot teacher (superadmin may also be a pilot)."""
    pilot = await get_enabled_pilot(db, int(user.id))
    if pilot is not None:
        return pilot
    if is_superadmin(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Use admin Learning Space APIs for superadmin operations",
        )
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a pilot teacher")


async def get_class_for_teacher(
    db: AsyncSession,
    class_id: int,
    teacher_user_id: int,
    *,
    allow_archived: bool = False,
) -> LearningClass:
    """Load class owned by teacher or raise 404."""
    result = await db.execute(select(LearningClass).where(LearningClass.id == class_id))
    learning_class = result.scalar_one_or_none()
    if learning_class is None or int(learning_class.teacher_user_id) != int(teacher_user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")
    if not allow_archived and learning_class.status != CLASS_STATUS_ACTIVE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Class is archived")
    return learning_class


async def get_class_for_staff(
    db: AsyncSession,
    class_id: int,
    user_id: int,
    *,
    allow_archived: bool = False,
    publish: bool = False,
) -> LearningClass:
    """Class owner, or assistant when publish is False."""
    learning_class = await db.get(LearningClass, class_id)
    if learning_class is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")
    if int(learning_class.teacher_user_id) == int(user_id):
        if not allow_archived and learning_class.status != CLASS_STATUS_ACTIVE:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Class is archived")
        return learning_class
    if not publish and await is_class_assistant(db, user_id, class_id):
        if not allow_archived and learning_class.status != CLASS_STATUS_ACTIVE:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Class is archived")
        return learning_class
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")


async def require_class_learner(db: AsyncSession, user: User, class_id: int) -> None:
    """Allow classroom students (after password change) or enrolled learners."""
    if is_student(user):
        require_student_password_ok(user)
        if int(user.learning_class_id or 0) != int(class_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your class")
        learning_class = await db.get(LearningClass, class_id)
        if learning_class is None or learning_class.status != CLASS_STATUS_ACTIVE:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Class is disabled")
        return
    if await is_class_learner(db, int(user.id), class_id):
        learning_class = await db.get(LearningClass, class_id)
        if learning_class is None or learning_class.status != CLASS_STATUS_ACTIVE:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Class is disabled")
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your class")


def assert_assignment_visible_to_learner(assignment: LearningAssignment) -> None:
    """Draft homework must not be openable even when the id is guessed."""
    if assignment.status == ASSIGNMENT_STATUS_DRAFT:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")


async def get_active_class_by_code(db: AsyncSession, class_code: str) -> LearningClass | None:
    """Lookup active class by join code."""
    code = (class_code or "").strip().upper()
    if not code:
        return None
    result = await db.execute(
        select(LearningClass).where(
            LearningClass.class_code == code,
            LearningClass.status == CLASS_STATUS_ACTIVE,
        )
    )
    return result.scalar_one_or_none()


def require_student(user: User) -> None:
    """Raise if user is not a student."""
    if not is_student(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Students only")


def require_student_password_ok(user: User) -> None:
    """Block Learning Space actions until password is changed."""
    if getattr(user, "must_change_password", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Password change required",
        )
