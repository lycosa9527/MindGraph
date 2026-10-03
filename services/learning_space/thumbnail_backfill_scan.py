"""Load only the Learning Space rows whose card thumbnail is still missing."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import noload

from models.domain.learning_space import LearningAssignment, LearningSubmission
from services.learning_space.thumbnail_backfill import (
    THUMBNAIL_BATCH_LIMIT,
    collect_card_jobs,
    fill_missing_card_thumbnails,
)

# Postgres evaluates these in the database. Finished rows never leave the server,
# and a submission's diagram spec is loaded only for the page this request fills.
ASSIGNMENT_THUMBNAIL_OPEN = text(
    """
    COALESCE(ai_permissions->>'template_thumbnail_ref', '') NOT LIKE 'lsimg:%'
    OR EXISTS (
      SELECT 1
      FROM jsonb_array_elements(
        CASE
          WHEN jsonb_typeof(ai_permissions->'reference_diagrams') = 'array'
          THEN ai_permissions->'reference_diagrams'
          ELSE '[]'::jsonb
        END
      ) AS elem
      WHERE COALESCE(elem->>'id', '') <> ''
        AND COALESCE(elem->>'thumbnail', '') NOT LIKE 'lsimg:%'
        AND COALESCE(elem->>'thumbnail', '') NOT LIKE 'http://%'
        AND COALESCE(elem->>'thumbnail', '') NOT LIKE 'https://%'
    )
    """
)
SUBMISSION_THUMBNAIL_OPEN = text(
    """
    (diagram_id IS NOT NULL OR snapshot_spec IS NOT NULL)
    AND COALESCE(snapshot_spec->>'thumbnail', '') NOT LIKE 'lsimg:%'
    AND COALESCE(snapshot_spec->>'thumbnail', '') NOT LIKE 'http://%'
    AND COALESCE(snapshot_spec->>'thumbnail', '') NOT LIKE 'https://%'
    """
)


def _skipped_submission_ids(skip: set[str]) -> set[int]:
    ids: set[int] = set()
    for key in skip:
        if not key.startswith("submission:"):
            continue
        raw = key.split(":", 1)[1]
        if raw.isdigit():
            ids.add(int(raw))
    return ids


def _processed_count(result: dict[str, Any]) -> int:
    return int(result["stored"]) + int(result["generated"]) + len(result["failed_keys"]) + len(result["ready_keys"])


async def _count_open_assignments(db: AsyncSession) -> int:
    counted = await db.scalar(select(func.count()).select_from(LearningAssignment).where(ASSIGNMENT_THUMBNAIL_OPEN))
    return int(counted or 0)


async def _assignment_page(db: AsyncSession, offset: int) -> list[LearningAssignment]:
    rows = await db.execute(
        select(LearningAssignment)
        .where(ASSIGNMENT_THUMBNAIL_OPEN)
        .order_by(LearningAssignment.id.asc())
        .options(noload(LearningAssignment.learning_class))
        .offset(offset)
        .limit(THUMBNAIL_BATCH_LIMIT)
    )
    return list(rows.scalars().all())


async def _next_assignment_window(db: AsyncSession, skip: set[str]) -> tuple[list[LearningAssignment], int]:
    """Next assignments that still have a card to fill, plus rows after this page."""
    total = await _count_open_assignments(db)
    offset = 0
    while offset < total:
        window = await _assignment_page(db, offset)
        if not window:
            break
        offset += len(window)
        if collect_card_jobs(window, [], skip):
            return window, max(0, total - offset)
        if len(window) < THUMBNAIL_BATCH_LIMIT:
            break
    return [], 0


async def _count_open_submissions(db: AsyncSession, skip: set[str]) -> int:
    stmt = select(func.count()).select_from(LearningSubmission).where(SUBMISSION_THUMBNAIL_OPEN)
    skipped = _skipped_submission_ids(skip)
    if skipped:
        stmt = stmt.where(LearningSubmission.id.notin_(tuple(skipped)))
    counted = await db.scalar(stmt)
    return int(counted or 0)


async def _load_submission_window(db: AsyncSession, skip: set[str]) -> list[LearningSubmission]:
    stmt = select(LearningSubmission).where(SUBMISSION_THUMBNAIL_OPEN).order_by(LearningSubmission.id.asc())
    skipped = _skipped_submission_ids(skip)
    if skipped:
        stmt = stmt.where(LearningSubmission.id.notin_(tuple(skipped)))
    rows = await db.execute(
        stmt.options(
            noload(LearningSubmission.assignment),
            noload(LearningSubmission.student),
        ).limit(THUMBNAIL_BATCH_LIMIT)
    )
    return list(rows.scalars().all())


async def backfill_missing_card_thumbnails(
    db: AsyncSession,
    *,
    skip: set[str] | None = None,
) -> dict[str, Any]:
    """Fill one batch. Diagram specs load only for the submissions this request draws."""
    ignored = skip or set()
    assignments, later_assignments = await _next_assignment_window(db, ignored)
    assignment_jobs = collect_card_jobs(assignments, [], ignored)
    open_submissions = await _count_open_submissions(db, ignored)
    if assignment_jobs:
        result = await fill_missing_card_thumbnails(db, assignments, [], skip=ignored)
        unprocessed = max(0, len(assignment_jobs) - _processed_count(result))
        result["remaining"] = unprocessed + later_assignments + open_submissions
        return result
    if open_submissions == 0:
        return await fill_missing_card_thumbnails(db, [], [], skip=ignored)
    window = await _load_submission_window(db, ignored)
    result = await fill_missing_card_thumbnails(db, [], window, skip=ignored)
    result["remaining"] = max(0, open_submissions - _processed_count(result))
    return result
