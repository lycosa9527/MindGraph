"""Upsert the seeded 双气泡图教程 and its COS cover."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.domain.training import TrainingCourse, TrainingCourseAsset, TrainingCourseStep
from services.features.training.courses.constants import (
    DOUBLE_BUBBLE_COVER_ID,
    DOUBLE_BUBBLE_COURSE_ID,
    DOUBLE_BUBBLE_DESCRIPTION,
    DOUBLE_BUBBLE_OPTIONS,
    DOUBLE_BUBBLE_STEP_ID,
    DOUBLE_BUBBLE_TITLE,
)
from services.features.training.courses.cover_png import build_double_bubble_cover_png
from services.features.training.storage.backend import put_bytes
from services.features.training.storage.keys import build_object_key


def _append_seed_step(course: TrainingCourse) -> None:
    """Attach the default canvas step when the tutorial has no steps yet."""
    course.steps.append(
        TrainingCourseStep(
            id=DOUBLE_BUBBLE_STEP_ID,
            course_id=course.id,
            position=0,
            step_type="canvas",
            payload={
                "diagram_type": "double_bubble_map",
                "topic_options": DOUBLE_BUBBLE_OPTIONS,
                "overlays": [],
                "page_key": "canvas",
                "pull_users": True,
            },
        )
    )


async def _ensure_seed_cover(db: AsyncSession, course: TrainingCourse) -> None:
    """Write the generated cover PNG only when the course has no cover yet."""
    logical_key = build_object_key(course.id, "cover", DOUBLE_BUBBLE_COVER_ID, ".png")
    png = build_double_bubble_cover_png()
    await put_bytes(logical_key, png, content_type="image/png")
    cover = next((row for row in course.assets if row.id == DOUBLE_BUBBLE_COVER_ID), None)
    if cover is None:
        cover = TrainingCourseAsset(
            id=DOUBLE_BUBBLE_COVER_ID,
            course_id=course.id,
            role="cover",
            logical_key=logical_key,
            mime="image/png",
            bytes_size=len(png),
        )
        db.add(cover)
        course.assets.append(cover)
    else:
        cover.logical_key = logical_key
        cover.mime = "image/png"
        cover.bytes_size = len(png)
    course.cover_asset_id = cover.id


async def ensure_double_bubble_seed(db: AsyncSession) -> TrainingCourse:
    """Create the default tutorial once; later author edits are kept."""
    result = await db.execute(
        select(TrainingCourse)
        .where(TrainingCourse.id == DOUBLE_BUBBLE_COURSE_ID)
        .options(selectinload(TrainingCourse.steps), selectinload(TrainingCourse.assets))
    )
    course = result.scalar_one_or_none()
    now = datetime.now(UTC)
    if course is None:
        course = TrainingCourse(
            id=DOUBLE_BUBBLE_COURSE_ID,
            owner_id=None,
            title=DOUBLE_BUBBLE_TITLE,
            description=DOUBLE_BUBBLE_DESCRIPTION,
            status="ready",
            is_system=True,
            created_at=now,
            updated_at=now,
        )
        db.add(course)
        await db.flush()
        _append_seed_step(course)
        await _ensure_seed_cover(db, course)
        await db.flush()
        return course

    course.is_system = True
    if not course.steps:
        _append_seed_step(course)
    if course.cover_asset_id is None and not any(row.role == "cover" for row in course.assets):
        await _ensure_seed_cover(db, course)
    await db.flush()
    return course
