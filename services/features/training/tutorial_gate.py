"""Required courses: unfinished courses play once; always-play courses play every visit.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Optional

from sqlalchemy import and_, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.training import TrainingCourse, TrainingCourseCompletion, TrainingCourseStep
from services.features.training.courses.serialize import serialize_course

READY = "ready"


def _flagged_course_ids(flag: str) -> Any:
    return select(TrainingCourseStep.course_id).where(TrainingCourseStep.payload[flag].astext == "true").distinct()


async def pending_required_course(db: AsyncSession, user_id: int) -> Optional[TrainingCourse]:
    """Earliest course that is still required, or marked to play on every visit."""
    completed = (
        select(TrainingCourseCompletion.course_id)
        .where(
            TrainingCourseCompletion.course_id == TrainingCourse.id,
            TrainingCourseCompletion.user_id == int(user_id),
        )
        .exists()
    )
    mandatory = TrainingCourse.id.in_(_flagged_course_ids("mandatory"))
    always_play = TrainingCourse.id.in_(_flagged_course_ids("always_play"))
    stmt = (
        select(TrainingCourse)
        .where(
            TrainingCourse.status == READY,
            or_(and_(mandatory, ~completed), always_play),
        )
        .order_by(TrainingCourse.created_at.asc(), TrainingCourse.id.asc())
        .limit(1)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def required_course_payload(db: AsyncSession, user_id: int, locale: str) -> Optional[dict[str, Any]]:
    """Serialized course, or None when nothing is outstanding."""
    course = await pending_required_course(db, user_id)
    if course is None or not course.steps:
        return None
    return serialize_course(course, locale=locale, include_steps=True)


async def _is_gate_ready(db: AsyncSession, course_id: str) -> bool:
    course = await db.get(TrainingCourse, course_id)
    if course is None or course.status != READY:
        return False
    found = await db.scalar(
        select(TrainingCourseStep.id)
        .where(
            TrainingCourseStep.course_id == course_id,
            or_(
                TrainingCourseStep.payload["mandatory"].astext == "true",
                TrainingCourseStep.payload["always_play"].astext == "true",
            ),
        )
        .limit(1)
    )
    return found is not None


async def complete_required_course(db: AsyncSession, user_id: int, course_id: str) -> None:
    """Record that the user finished this required course."""
    if not await _is_gate_ready(db, course_id):
        raise ValueError("not_required")
    stmt = (
        pg_insert(TrainingCourseCompletion)
        .values(
            user_id=int(user_id),
            course_id=course_id,
            completed_at=datetime.now(UTC),
        )
        .on_conflict_do_nothing(index_elements=["user_id", "course_id"])
    )
    await db.execute(stmt)
