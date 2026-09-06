"""Upsert the seeded 双气泡图教程 and its COS cover."""

from __future__ import annotations

import asyncio
import logging
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
from services.features.training.training_logger import bilingual_label, log_training

logger = logging.getLogger(__name__)


class _SeedOnceHolder:
    """Remember a successful seed without a global statement."""

    def __init__(self) -> None:
        self.done = False
        self.lock = asyncio.Lock()


_SEED_ONCE = _SeedOnceHolder()


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
    log_training(
        logger,
        "seed_cover_written",
        prefix="[Training/COS]",
        course_id=course.id,
        key=logical_key,
        bytes=len(png),
    )


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
        log_training(
            logger,
            "seed_course_created",
            course_id=course.id,
            title=bilingual_label(course.title),
            steps=len(course.steps),
        )
        return course

    course.is_system = True
    appended_step = False
    if not course.steps:
        _append_seed_step(course)
        appended_step = True
    wrote_cover = course.cover_asset_id is None and not any(row.role == "cover" for row in course.assets)
    if wrote_cover:
        await _ensure_seed_cover(db, course)
    await db.flush()
    if appended_step or wrote_cover:
        log_training(
            logger,
            "seed_course_repaired",
            course_id=course.id,
            appended_step=appended_step,
            wrote_cover=wrote_cover,
        )
    return course


async def ensure_double_bubble_seed_once(db: AsyncSession) -> None:
    """Seed at most once per process; catalog list is the only caller."""
    if _SEED_ONCE.done:
        return
    async with _SEED_ONCE.lock:
        if _SEED_ONCE.done:
            return
        await ensure_double_bubble_seed(db)
        _SEED_ONCE.done = True
