"""Training course persistence helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.domain.training import TrainingCourse, TrainingCourseAsset, TrainingCourseStep
from services.features.training.courses.constants import (
    COURSE_STATUSES,
    FOCUS_KEYS,
    MODAL_KEYS,
    PAGE_KEYS,
    STEP_TYPES,
    clamped_mark_step,
    optional_notes,
    optional_step_key,
)
from services.features.training.storage.backend import delete_course_prefix


async def list_courses(db: AsyncSession) -> list[TrainingCourse]:
    """All courses, system first then recently updated."""
    result = await db.execute(
        select(TrainingCourse)
        .options(selectinload(TrainingCourse.steps), selectinload(TrainingCourse.assets))
        .order_by(TrainingCourse.is_system.desc(), TrainingCourse.updated_at.desc())
    )
    return list(result.scalars().unique().all())


async def get_course(db: AsyncSession, course_id: str) -> Optional[TrainingCourse]:
    """Load one course with steps and assets."""
    result = await db.execute(
        select(TrainingCourse)
        .where(TrainingCourse.id == course_id)
        .options(selectinload(TrainingCourse.steps), selectinload(TrainingCourse.assets))
    )
    return result.scalar_one_or_none()


async def create_course(
    db: AsyncSession,
    *,
    owner_id: Optional[int],
    title: dict[str, str],
    description: dict[str, str],
) -> TrainingCourse:
    """Insert a draft course."""
    course = TrainingCourse(
        owner_id=owner_id,
        title=title,
        description=description,
        status="draft",
        is_system=False,
    )
    db.add(course)
    await db.flush()
    return course


def _normalize_bilingual(value: Any, fallback: dict[str, str]) -> dict[str, str]:
    if isinstance(value, dict):
        zh = str(value.get("zh") or value.get("en") or "").strip()
        en = str(value.get("en") or value.get("zh") or "").strip()
        if zh or en:
            return {"zh": zh or en, "en": en or zh}
    if isinstance(value, str) and value.strip():
        text = value.strip()
        return {"zh": text, "en": text}
    return fallback


async def save_course(
    db: AsyncSession,
    course: TrainingCourse,
    *,
    title: Any = None,
    description: Any = None,
    status: Optional[str] = None,
    steps: Optional[list[dict[str, Any]]] = None,
) -> TrainingCourse:
    """Update title/description/status and optionally replace steps."""
    if title is not None:
        course.title = _normalize_bilingual(title, course.title or {"zh": "", "en": ""})
    if description is not None:
        course.description = _normalize_bilingual(description, course.description or {"zh": "", "en": ""})
    if status is not None:
        if status not in COURSE_STATUSES:
            raise ValueError("Invalid course status")
        course.status = status
    if steps is not None:
        course.steps.clear()
        await db.flush()
        for index, raw in enumerate(steps):
            step_type = str(raw.get("type") or raw.get("step_type") or "")
            if step_type not in STEP_TYPES:
                raise ValueError(f"Invalid step type: {step_type}")
            page_key = raw.get("page_key")
            if isinstance(page_key, str):
                page_key = page_key.strip() or None
            if page_key is not None and str(page_key) not in PAGE_KEYS:
                raise ValueError(f"Invalid page_key: {page_key}")
            canvas_mode = raw.get("mindmap_canvas_mode")
            if isinstance(canvas_mode, str):
                canvas_mode = canvas_mode.strip() or None
            if canvas_mode is not None and canvas_mode not in {"legacy", "v2", "v3"}:
                raise ValueError(f"Invalid mindmap_canvas_mode: {canvas_mode}")
            modal_key = optional_step_key(raw.get("modal_key"), MODAL_KEYS, "modal_key")
            focus_key = optional_step_key(raw.get("focus_key"), FOCUS_KEYS, "focus_key")
            notes = optional_notes(raw.get("notes"))
            payload = {
                "diagram_type": raw.get("diagram_type"),
                "topic_options": raw.get("topic_options") or [],
                "asset_id": raw.get("asset_id"),
                "thumb_id": raw.get("thumb_id"),
                "overlays": raw.get("overlays") or [],
                "page_key": page_key,
                "pull_users": bool(raw.get("pull_users")),
                "mindmap_canvas_mode": canvas_mode,
                "modal_key": modal_key,
                "focus_key": focus_key,
                "notes": notes,
                "mark_step": clamped_mark_step(raw.get("mark_step"), 1),
                "mark_steps": clamped_mark_step(raw.get("mark_steps"), 1),
            }
            course.steps.append(
                TrainingCourseStep(
                    position=index,
                    step_type=step_type,
                    payload=payload,
                )
            )
    course.updated_at = datetime.now(UTC)
    await db.flush()
    return course


async def add_asset(
    db: AsyncSession,
    course: TrainingCourse,
    *,
    asset_id: str,
    role: str,
    logical_key: str,
    mime: str,
    bytes_size: int,
) -> TrainingCourseAsset:
    """Bind a completed upload to the course."""
    existing = next((row for row in course.assets if row.id == asset_id), None)
    if existing is not None:
        existing.logical_key = logical_key
        existing.mime = mime
        existing.bytes_size = bytes_size
        existing.role = role
        asset = existing
    else:
        asset = TrainingCourseAsset(
            id=asset_id,
            course_id=course.id,
            role=role,
            logical_key=logical_key,
            mime=mime,
            bytes_size=bytes_size,
        )
        db.add(asset)
        course.assets.append(asset)
    if role == "cover":
        course.cover_asset_id = asset.id
    course.updated_at = datetime.now(UTC)
    await db.flush()
    return asset


async def delete_course(db: AsyncSession, course: TrainingCourse) -> None:
    """Remove course rows and the COS folder."""
    course_id = course.id
    await db.delete(course)
    await db.flush()
    delete_course_prefix(course_id)
