"""
Showcase field options — DB-backed subjects, grades, recommended tags.

Meta payload is cached in Redis (multi-worker safe).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.showcase_admin import ShowcaseFieldOption
from routers.features.showcase_constants import (
    GRADE_ORDER,
    GRADES,
    SUBJECT_ORDER,
    SUBJECTS,
)
from services.redis.cache import redis_showcase_cache as showcase_cache


async def invalidate_field_options_cache_async() -> None:
    """Async Redis meta invalidation."""
    await showcase_cache.invalidate_meta()


def _sort_by_canonical_order(values: list[str], canonical: tuple[str, ...]) -> list[str]:
    """Sort values by canonical order, then alphabetically for unknowns."""
    rank = {value: idx for idx, value in enumerate(canonical)}
    return sorted(values, key=lambda value: (rank.get(value, len(canonical)), value))


async def load_active_values(db: AsyncSession, category: str) -> list[str]:
    """Load active field-option values for a category, ordered for UI display."""
    rows = (
        await db.execute(
            select(ShowcaseFieldOption.value)
            .where(
                ShowcaseFieldOption.category == category,
                ShowcaseFieldOption.is_active.is_(True),
            )
            .order_by(ShowcaseFieldOption.sort_order, ShowcaseFieldOption.value)
        )
    ).all()
    values = [row[0] for row in rows]
    if category == "grade":
        values = _sort_by_canonical_order(values, GRADE_ORDER)
    elif category == "subject":
        values = _sort_by_canonical_order(values, SUBJECT_ORDER)
    return values


async def load_meta_payload(db: AsyncSession) -> dict:
    """Return subjects/grades/tags meta, using Redis cache when available."""
    cached = await showcase_cache.get_cached_meta()
    if isinstance(cached, dict):
        return cached

    subjects = await load_active_values(db, "subject")
    grades = await load_active_values(db, "grade")
    recommended_tags = await load_active_values(db, "recommended_tag")

    if not subjects:
        subjects = list(SUBJECT_ORDER)
    if not grades:
        grades = list(GRADE_ORDER)

    payload = {
        "subjects": subjects,
        "grades": grades,
        "recommended_tags": recommended_tags,
    }
    await showcase_cache.set_cached_meta(payload)
    return payload


async def validate_subject(db: AsyncSession, value: Optional[str]) -> None:
    """Raise ValueError when subject is set and not in the active allow-list."""
    if value is None:
        return
    allowed = set(await load_active_values(db, "subject"))
    if not allowed:
        allowed = set(SUBJECTS)
    if value not in allowed:
        raise ValueError("Invalid subject")


async def validate_grade(db: AsyncSession, value: Optional[str]) -> None:
    """Raise ValueError when grade is set and not in the active allow-list."""
    if value is None:
        return
    allowed = set(await load_active_values(db, "grade"))
    if not allowed:
        allowed = set(GRADES)
    if value not in allowed:
        raise ValueError("Invalid grade")
