"""In-process cache of serialized course steps for live play."""

from __future__ import annotations

from typing import Any

from services.features.training.courses.repository import get_course
from services.features.training.courses.serialize import serialize_course
from utils.db.session_open import system_rls_session

_CACHE: dict[str, tuple[str, list[dict[str, Any]]]] = {}
_CACHE_MAX = 32


def _stamp(course_id: str, updated_at: Any) -> str:
    if updated_at is None:
        return f"{course_id}:"
    iso = updated_at.isoformat() if hasattr(updated_at, "isoformat") else str(updated_at)
    return f"{course_id}:{iso}"


def _remember(course_id: str, stamp: str, steps: list[dict[str, Any]]) -> None:
    if len(_CACHE) >= _CACHE_MAX and course_id not in _CACHE:
        _CACHE.pop(next(iter(_CACHE)))
    _CACHE[course_id] = (stamp, steps)


async def load_serialized_steps(course_id: str) -> list[dict[str, Any]]:
    """Return steps for play/step, keyed by course id + updated_at."""
    async with system_rls_session() as db:
        course = await get_course(db, course_id)
        if course is None:
            return []
        stamp = _stamp(course.id, course.updated_at)
        cached = _CACHE.get(course.id)
        if cached is not None and cached[0] == stamp:
            return cached[1]
        body = serialize_course(course, include_steps=True)
        steps = body.get("steps") or []
        _remember(course.id, stamp, steps)
        return steps
