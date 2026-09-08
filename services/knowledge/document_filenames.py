"""Allocate space-unique ``knowledge_documents.file_name`` values.

``uq_space_filename`` is ``(space_id, file_name)`` across every package in a
user's knowledge space. Paste/web ingest defaults to a generic title such as
``Pasted note.md``, so callers must suffix before INSERT.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.knowledge_space import KnowledgeDocument

FILE_NAME_MAX_LEN = 255
_MAX_SUFFIX = 10_000
_INSERT_RETRIES = 3

T = TypeVar("T")


async def existing_space_file_names(db: AsyncSession, space_id: int) -> set[str]:
    """Return every file_name already stored in the given knowledge space."""
    result = await db.execute(select(KnowledgeDocument.file_name).where(KnowledgeDocument.space_id == space_id))
    return {name for name in result.scalars().all() if name}


def _clip_file_name(stem: str, suffix: str, extra: str = "") -> str:
    """Keep ``stem + extra + suffix`` within the ``file_name`` column limit."""
    budget = FILE_NAME_MAX_LEN - len(extra) - len(suffix)
    if budget < 1:
        return f"{extra}{suffix}"[:FILE_NAME_MAX_LEN]
    return f"{stem[:budget]}{extra}{suffix}"


def next_unique_file_name(file_name: str, taken: set[str]) -> str:
    """Return ``file_name`` or ``stem_N.ext`` when that name is already taken."""
    path = Path(file_name)
    suffix = path.suffix
    stem = path.stem
    candidate = _clip_file_name(stem, suffix)
    if candidate not in taken:
        return candidate
    for index in range(1, _MAX_SUFFIX + 1):
        candidate = _clip_file_name(stem, suffix, f"_{index}")
        if candidate not in taken:
            return candidate
    raise ValueError(f"Could not allocate a unique file name for '{file_name}'")


async def allocate_unique_file_name(db: AsyncSession, space_id: int, file_name: str) -> str:
    """Pick a ``uq_space_filename``-safe name for an upcoming INSERT."""
    taken = await existing_space_file_names(db, space_id)
    return next_unique_file_name(file_name, taken)


async def insert_unique_named_row(
    db: AsyncSession,
    space_id: int,
    desired_name: str,
    build: Callable[[str], T],
) -> T:
    """INSERT a row, retrying with a new suffix if ``uq_space_filename`` races."""
    extra_taken: set[str] = set()
    last_error: IntegrityError | None = None
    for _ in range(_INSERT_RETRIES):
        taken = await existing_space_file_names(db, space_id)
        taken.update(extra_taken)
        name = next_unique_file_name(desired_name, taken)
        row = build(name)
        db.add(row)
        try:
            await db.commit()
            await db.refresh(row)
            return row
        except IntegrityError as exc:
            last_error = exc
            extra_taken.add(name)
            await db.rollback()
    if last_error is None:
        raise RuntimeError("unique file name insert failed")
    raise last_error
