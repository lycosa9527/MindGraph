"""Allocate globally unique Learning Space class codes without listing every school.

RLS only shows the current school's codes, so uniqueness is enforced by the
database unique constraint and a short retry loop.
"""

from __future__ import annotations

import logging

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.learning_space import LearningClass
from services.learning_space.passwords import generate_class_code
from services.utils.error_types import DATABASE_ERRORS

logger = logging.getLogger(__name__)


async def create_class_with_unique_code(
    db: AsyncSession,
    *,
    name: str,
    teacher_user_id: int,
    organization_id: int,
    class_status: str,
    max_students: int,
) -> LearningClass:
    """Insert a class, retrying when the generated code collides globally."""
    last_error: IntegrityError | None = None
    for attempt in range(8):
        length = 6 if attempt < 5 else 8
        learning_class = LearningClass(
            name=name,
            class_code=generate_class_code(length),
            teacher_user_id=teacher_user_id,
            organization_id=organization_id,
            status=class_status,
            max_students=max_students,
        )
        db.add(learning_class)
        try:
            await db.commit()
            await db.refresh(learning_class)
            logger.info(
                "[LearningSpace] Class created id=%s teacher=%s org=%s",
                learning_class.id,
                teacher_user_id,
                organization_id,
            )
            return learning_class
        except IntegrityError as exc:
            last_error = exc
            await db.rollback()
        except DATABASE_ERRORS as exc:
            await db.rollback()
            logger.error(
                "[LearningSpace] Class create failed teacher=%s org=%s: %s",
                teacher_user_id,
                organization_id,
                exc,
            )
            raise
    logger.error(
        "[LearningSpace] Class code allocation exhausted teacher=%s org=%s",
        teacher_user_id,
        organization_id,
    )
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Could not allocate class code",
    ) from last_error


async def rotate_class_code(db: AsyncSession, class_id: int) -> LearningClass:
    """Assign a new unique class code; retry on a global collision."""
    last_error: IntegrityError | None = None
    for attempt in range(8):
        learning_class = await db.get(LearningClass, class_id)
        if learning_class is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")
        length = 6 if attempt < 5 else 8
        learning_class.class_code = generate_class_code(length)
        try:
            await db.commit()
            await db.refresh(learning_class)
            logger.info("[LearningSpace] Class code rotated class=%s", class_id)
            return learning_class
        except IntegrityError as exc:
            last_error = exc
            await db.rollback()
        except DATABASE_ERRORS as exc:
            await db.rollback()
            logger.error("[LearningSpace] Class code rotate failed class=%s: %s", class_id, exc)
            raise
    logger.error("[LearningSpace] Class code rotate exhausted class=%s", class_id)
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Could not allocate class code",
    ) from last_error


def class_code_in_use_error() -> HTTPException:
    """HTTP 400 when the unique class_code constraint fires."""
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Class code already in use",
    )
