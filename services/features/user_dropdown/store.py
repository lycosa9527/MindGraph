"""Persistence and serialization for user dropdown menu items."""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.domain.training import TrainingCourse
from models.domain.user_dropdown import UserDropdownItem, generate_user_dropdown_id
from services.features.training.courses.repository import get_course
from services.features.training.courses.serialize import localized_text, serialize_course

MAX_ITEMS = 30
MAX_LABEL = 40


def clean_label(raw: str) -> str:
    """Trim a menu label and reject blanks or overlong names."""
    label = raw.strip()
    if not label:
        raise ValueError("user_dropdown_label_required")
    if len(label) > MAX_LABEL:
        raise ValueError("user_dropdown_label_too_long")
    return label


def locale_of(user: object) -> str:
    """Preferred language on a user or admin actor."""
    lang = getattr(user, "preferred_language", None) or "zh"
    return str(lang)


def serialize_menu_item(item: UserDropdownItem, locale: str) -> dict[str, Any]:
    """One dropdown row for admin and the signed-in menu."""
    title = ""
    course = item.course
    if course is not None:
        title = localized_text(course.title, locale)
    return {
        "id": item.id,
        "label": item.label,
        "course_id": item.course_id,
        "course_title": title,
        "sort_order": item.sort_order,
    }


def serialize_course_option(course: TrainingCourse, locale: str) -> dict[str, str]:
    """Course the admin picker can link."""
    return {
        "id": course.id,
        "title": localized_text(course.title, locale) or course.id,
        "status": course.status,
    }


async def list_items(db: AsyncSession) -> list[UserDropdownItem]:
    """Menu rows in display order."""
    result = await db.execute(
        select(UserDropdownItem)
        .options(selectinload(UserDropdownItem.course))
        .order_by(UserDropdownItem.sort_order, UserDropdownItem.created_at)
    )
    return list(result.scalars().all())


async def get_item(db: AsyncSession, item_id: str) -> Optional[UserDropdownItem]:
    """One row, or None."""
    result = await db.execute(
        select(UserDropdownItem).options(selectinload(UserDropdownItem.course)).where(UserDropdownItem.id == item_id)
    )
    return result.scalar_one_or_none()


async def create_item(db: AsyncSession, label: str) -> UserDropdownItem:
    """Append a function with no course yet."""
    count_result = await db.execute(select(func.count()).select_from(UserDropdownItem))
    if int(count_result.scalar_one()) >= MAX_ITEMS:
        raise ValueError("user_dropdown_limit")
    order_result = await db.execute(select(func.max(UserDropdownItem.sort_order)))
    sort_order = int(order_result.scalar_one() or 0) + 1
    item = UserDropdownItem(
        id=generate_user_dropdown_id(),
        label=clean_label(label),
        sort_order=sort_order,
    )
    db.add(item)
    await db.flush()
    return item


async def rename_item(item: UserDropdownItem, label: str) -> None:
    """Replace the menu label."""
    item.label = clean_label(label)


async def assign_course(db: AsyncSession, item: UserDropdownItem, course_id: Optional[str]) -> None:
    """Link a built course, or clear the link."""
    cleaned = (course_id or "").strip()
    if not cleaned:
        item.course_id = None
        item.course = None
        return
    course = await get_course(db, cleaned)
    if course is None:
        raise ValueError("user_dropdown_course_missing")
    item.course_id = course.id
    item.course = course


async def delete_item(db: AsyncSession, item: UserDropdownItem) -> None:
    """Remove a menu function."""
    await db.delete(item)
    await db.flush()


def menu_payload(items: list[UserDropdownItem], courses: list[TrainingCourse], locale: str) -> dict[str, Any]:
    """Admin catalog: functions plus courses that can be linked."""
    return {
        "items": [serialize_menu_item(item, locale) for item in items],
        "courses": [serialize_course_option(course, locale) for course in courses],
    }


def public_menu_payload(items: list[UserDropdownItem], locale: str) -> dict[str, Any]:
    """Signed-in menu: only functions that already link a course."""
    linked = [item for item in items if item.course_id]
    return {"items": [serialize_menu_item(item, locale) for item in linked]}


def course_for_item(item: UserDropdownItem, locale: str) -> dict[str, Any]:
    """Walkthrough payload for a linked course."""
    course = item.course
    if course is None or not item.course_id:
        raise ValueError("user_dropdown_course_missing")
    return serialize_course(course, locale=locale, include_steps=True)
