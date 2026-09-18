"""Student import and password reset for Learning Space.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import User
from models.domain.learning_space import LearningClass
from services.learning_space.memberships import count_class_learners, count_classroom_students
from services.learning_space.passwords import (
    initial_password_from_name,
    normalize_student_name,
    student_synthetic_email,
)
from services.redis.session.redis_session_manager import get_session_manager
from services.utils.error_types import BACKGROUND_INFRA_ERRORS
from utils.auth.password import hash_password
from utils.auth.role_constants import ROLE_STUDENT

logger = logging.getLogger(__name__)


@dataclass
class ImportPreviewRow:
    """One CSV row after validation."""

    name: str
    initial_password: str
    ok: bool
    error: str | None = None


@dataclass
class ImportResult:
    """Import batch outcome."""

    created: list[dict]
    failed: list[dict]


async def count_class_students(db: AsyncSession, class_id: int) -> int:
    """Roster size: classroom students plus enrolled learners (not assistants)."""
    classroom = await count_classroom_students(db, class_id)
    learners = await count_class_learners(db, class_id)
    return classroom + learners


def preview_student_names(names: list[str]) -> list[ImportPreviewRow]:
    """Validate names and show generated initial passwords (no DB writes)."""
    seen: set[str] = set()
    rows: list[ImportPreviewRow] = []
    for raw in names:
        name = normalize_student_name(raw)
        if not name:
            rows.append(ImportPreviewRow(name=raw or "", initial_password="", ok=False, error="empty_name"))
            continue
        if name in seen:
            rows.append(
                ImportPreviewRow(
                    name=name,
                    initial_password="",
                    ok=False,
                    error="duplicate_name_in_file",
                )
            )
            continue
        seen.add(name)
        rows.append(
            ImportPreviewRow(
                name=name,
                initial_password=initial_password_from_name(name),
                ok=True,
            )
        )
    return rows


async def import_students(
    db: AsyncSession,
    learning_class: LearningClass,
    names: list[str],
) -> ImportResult:
    """Create student users for unique names; skip conflicts."""
    preview = preview_student_names(names)
    existing_result = await db.execute(
        select(User.name).where(
            User.learning_class_id == learning_class.id,
            User.role == ROLE_STUDENT,
        )
    )
    existing_names = {normalize_student_name(n) for (n,) in existing_result.all() if n}
    current_count = await count_class_students(db, learning_class.id)
    created: list[dict] = []
    failed: list[dict] = []

    for row in preview:
        if not row.ok:
            failed.append({"name": row.name, "error": row.error})
            continue
        if row.name in existing_names:
            failed.append({"name": row.name, "error": "duplicate_name_in_class"})
            continue
        if current_count + len(created) >= int(learning_class.max_students):
            failed.append({"name": row.name, "error": "class_full"})
            continue
        temp_email = f"pending.{uuid.uuid4().hex}@student.learning.local"
        user = User(
            email=temp_email,
            phone=None,
            name=row.name,
            password_hash=hash_password(row.initial_password),
            role=ROLE_STUDENT,
            organization_id=learning_class.organization_id,
            learning_class_id=learning_class.id,
            must_change_password=True,
            login_password_set=True,
        )
        db.add(user)
        await db.flush()
        user.email = student_synthetic_email(learning_class.id, int(user.id))
        existing_names.add(row.name)
        created.append(
            {
                "id": user.id,
                "name": row.name,
                "initial_password": row.initial_password,
            }
        )

    await db.commit()
    return ImportResult(created=created, failed=failed)


async def reset_student_password(db: AsyncSession, student: User) -> str:
    """Reset to rule-based initial password and force change."""
    name = normalize_student_name(student.name or "")
    plain = initial_password_from_name(name)
    student.password_hash = hash_password(plain)
    student.must_change_password = True
    await db.commit()
    await db.refresh(student)
    logger.info("[LearningSpace] Password reset for student_id=%s", student.id)
    return plain


async def classroom_student_ids(db: AsyncSession, class_id: int) -> list[int]:
    """User ids of dedicated classroom student accounts in a class."""
    result = await db.execute(select(User.id).where(User.learning_class_id == class_id, User.role == ROLE_STUDENT))
    return [int(uid) for (uid,) in result.all()]


async def kick_classroom_student_sessions(student_ids: list[int]) -> None:
    """Drop live sessions so disabled-class students cannot stay signed in."""
    if not student_ids:
        return
    try:
        manager = get_session_manager()
    except BACKGROUND_INFRA_ERRORS:
        logger.warning("[LearningSpace] Session manager unavailable; skip student kick")
        return
    for user_id in student_ids:
        try:
            await manager.invalidate_user_sessions(user_id)
        except BACKGROUND_INFRA_ERRORS as exc:
            logger.warning("[LearningSpace] Failed to invalidate sessions for student %s: %s", user_id, exc)
