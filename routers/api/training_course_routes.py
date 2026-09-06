"""Training course CRUD for Course Builder."""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from models.domain.auth import User
from services.features.training.courses.repository import (
    create_course,
    delete_course,
    get_course,
    list_courses,
    save_course,
)
from services.features.training.courses.seed import ensure_double_bubble_seed_once
from services.features.training.courses.serialize import serialize_course
from services.features.training.permissions import (
    can_delete_training_course,
    can_lead_any_training,
)
from services.features.training.training_logger import (
    bilingual_label,
    log_training,
    step_type_summary,
)
from utils.auth import get_current_user
from utils.db.session_open import system_rls_session

logger = logging.getLogger(__name__)

router = APIRouter()


class CourseWriteBody(BaseModel):
    """Create or update a course."""

    title: Any = None
    description: Any = None
    status: Optional[str] = Field(default=None, max_length=20)
    steps: Optional[list[dict[str, Any]]] = None


def _require_author(user: User) -> None:
    if not can_lead_any_training(user):
        raise HTTPException(status_code=403, detail="Training author access required")


def _locale_from_user(user: User) -> str:
    lang = getattr(user, "preferred_language", None) or "zh"
    return str(lang)


@router.get("/courses")
async def list_training_courses(
    locale: str = Query(default=""),
    current_user: User = Depends(get_current_user),
):
    """Landing + builder catalog."""
    _require_author(current_user)
    lang = locale or _locale_from_user(current_user)
    async with system_rls_session() as db:
        await ensure_double_bubble_seed_once(db)
        await db.commit()
        rows = await list_courses(db)
        return {"items": [serialize_course(row, locale=lang, include_steps=False) for row in rows]}


@router.post("/courses")
async def create_training_course(
    body: CourseWriteBody,
    current_user: User = Depends(get_current_user),
):
    """Create a draft course."""
    _require_author(current_user)
    title = body.title if body.title is not None else {"zh": "未命名课程", "en": "Untitled course"}
    description = body.description if body.description is not None else {"zh": "", "en": ""}
    async with system_rls_session() as db:
        course = await create_course(
            db,
            owner_id=int(current_user.id),
            title={"zh": "", "en": ""},
            description={"zh": "", "en": ""},
        )
        course = await save_course(db, course, title=title, description=description)
        await db.commit()
        await db.refresh(course)
        loaded = await get_course(db, course.id)
    saved = loaded or course
    log_training(
        logger,
        "course_created",
        actor_id=int(current_user.id),
        course_id=saved.id,
        owner_id=int(current_user.id),
        title=bilingual_label(saved.title),
        status=saved.status,
    )
    return serialize_course(saved, locale=_locale_from_user(current_user))


@router.get("/courses/{course_id}")
async def get_training_course(
    course_id: str,
    current_user: User = Depends(get_current_user),
):
    """Builder editor payload."""
    _require_author(current_user)
    async with system_rls_session() as db:
        course = await get_course(db, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    return serialize_course(course, locale=_locale_from_user(current_user))


@router.put("/courses/{course_id}")
async def update_training_course(
    course_id: str,
    body: CourseWriteBody,
    current_user: User = Depends(get_current_user),
):
    """Save title, status, and steps."""
    _require_author(current_user)
    async with system_rls_session() as db:
        course = await get_course(db, course_id)
        if course is None:
            raise HTTPException(status_code=404, detail="Course not found")
        try:
            await save_course(
                db,
                course,
                title=body.title,
                description=body.description,
                status=body.status,
                steps=body.steps,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        await db.commit()
        loaded = await get_course(db, course_id)
    saved = loaded or course
    log_training(
        logger,
        "course_saved",
        actor_id=int(current_user.id),
        course_id=saved.id,
        title=bilingual_label(saved.title),
        status=saved.status,
        steps=step_type_summary(body.steps),
        system=bool(saved.is_system),
    )
    return serialize_course(saved, locale=_locale_from_user(current_user))


@router.delete("/courses/{course_id}")
async def remove_training_course(
    course_id: str,
    current_user: User = Depends(get_current_user),
):
    """Delete a non-system course and its COS folder."""
    _require_author(current_user)
    async with system_rls_session() as db:
        course = await get_course(db, course_id)
        if course is None:
            raise HTTPException(status_code=404, detail="Course not found")
        if not can_delete_training_course(current_user, course):
            detail = "System courses cannot be deleted" if course.is_system else "Only the owner may delete this course"
            raise HTTPException(status_code=403, detail=detail)
        title = bilingual_label(course.title)
        await delete_course(db, course)
        await db.commit()
    log_training(
        logger,
        "course_deleted",
        actor_id=int(current_user.id),
        course_id=course_id,
        title=title,
    )
    return {"ok": True}
