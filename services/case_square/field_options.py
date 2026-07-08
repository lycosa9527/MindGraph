"""
Case Square field options — DB-backed subjects, grades, recommended tags.
"""

from __future__ import annotations

import time
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.case_square_admin import CaseSquareFieldOption
from routers.features.case_square_constants import (
    GRADE_ORDER,
    GRADES,
    SUBJECT_ORDER,
    SUBJECTS,
)

_CACHE_TTL_SECONDS = 300.0
_cache: dict[str, tuple[float, object]] = {}


def _cache_get(key: str):
    entry = _cache.get(key)
    if not entry:
        return None
    ts, value = entry
    if time.monotonic() - ts > _CACHE_TTL_SECONDS:
        _cache.pop(key, None)
        return None
    return value


def _cache_set(key: str, value: object) -> None:
    _cache[key] = (time.monotonic(), value)


def invalidate_field_options_cache() -> None:
    _cache.clear()


def _sort_by_canonical_order(values: list[str], canonical: tuple[str, ...]) -> list[str]:
    rank = {value: idx for idx, value in enumerate(canonical)}
    return sorted(values, key=lambda value: (rank.get(value, len(canonical)), value))


async def load_active_values(db: AsyncSession, category: str) -> list[str]:
    cache_key = f"values:{category}"
    cached = _cache_get(cache_key)
    if isinstance(cached, list):
        return cached

    rows = (
        await db.execute(
            select(CaseSquareFieldOption.value)
            .where(
                CaseSquareFieldOption.category == category,
                CaseSquareFieldOption.is_active.is_(True),
            )
            .order_by(CaseSquareFieldOption.sort_order, CaseSquareFieldOption.value)
        )
    ).all()
    values = [row[0] for row in rows]
    if category == "grade":
        values = _sort_by_canonical_order(values, GRADE_ORDER)
    elif category == "subject":
        values = _sort_by_canonical_order(values, SUBJECT_ORDER)
    _cache_set(cache_key, values)
    return values


async def load_meta_payload(db: AsyncSession) -> dict:
    cache_key = "meta"
    cached = _cache_get(cache_key)
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
    _cache_set(cache_key, payload)
    return payload


async def validate_subject(db: AsyncSession, value: Optional[str]) -> None:
    if value is None:
        return
    allowed = set(await load_active_values(db, "subject"))
    if not allowed:
        allowed = set(SUBJECTS)
    if value not in allowed:
        raise ValueError("Invalid subject")


async def validate_grade(db: AsyncSession, value: Optional[str]) -> None:
    if value is None:
        return
    allowed = set(await load_active_values(db, "grade"))
    if not allowed:
        allowed = set(GRADES)
    if value not in allowed:
        raise ValueError("Invalid grade")
