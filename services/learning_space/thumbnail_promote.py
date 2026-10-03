"""Persist Learning Space card thumbnails on COS when rows are read or opened."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.learning_space import LearningAssignment, LearningSubmission
from services.learning_space.passwords import merge_ai_permissions
from services.learning_space.thumbnail_storage import (
    assignment_thumbnail_promote_pending,
    assignment_thumbnails_changed,
    display_thumbnail,
    prepare_assignment_thumbnails_sync,
    promote_snapshot_thumbnail_sync,
    reference_ids_needing_library,
    reference_thumbnail_src,
)
from services.redis.cache.redis_diagram_cache import get_diagram_cache
from services.utils.error_types import BACKGROUND_INFRA_ERRORS, DATABASE_ERRORS

logger = logging.getLogger(__name__)


async def load_reference_diagram_preview(
    assignment: LearningAssignment,
    diagram_id: str,
) -> dict[str, Any]:
    """Return one look-only reference diagram for the opened card."""
    cleaned = (diagram_id or "").strip()
    raw = assignment.ai_permissions if isinstance(assignment.ai_permissions, dict) else None
    merged = merge_ai_permissions(raw)
    references = merged.get("reference_diagrams")
    match: dict[str, Any] | None = None
    match_index = -1
    if isinstance(references, list):
        for index, item in enumerate(references):
            if isinstance(item, dict) and str(item.get("id") or "").strip() == cleaned:
                match = item
                match_index = index
                break
    if match is None or not cleaned:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reference diagram not found")
    cache = get_diagram_cache()
    try:
        diagram = await cache.get_diagram(int(assignment.created_by), cleaned)
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.warning(
            "[LearningSpace] Reference preview unavailable assignment=%s diagram=%s: %s",
            assignment.id,
            cleaned,
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Diagram service unavailable",
        ) from exc
    if not diagram:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reference diagram not found")
    spec = diagram.get("spec")
    thumb_out = None
    if assignment.id is not None and match_index >= 0:
        thumb_out = display_thumbnail(
            match.get("thumbnail"),
            reference_thumbnail_src(int(assignment.id), match_index),
        )
    return {
        "diagram_id": cleaned,
        "title": str(diagram.get("title") or match.get("title") or ""),
        "diagram_type": str(diagram.get("diagram_type") or "mind_map"),
        "language": str(diagram.get("language") or "zh"),
        "preview_spec": spec if isinstance(spec, dict) else None,
        "thumbnail": thumb_out,
    }


async def reference_library_thumbnails(owner_id: int, permissions: object) -> dict[str, str]:
    """Teacher-library thumbnails for reference cards whose stored image was stripped."""
    if not isinstance(permissions, dict):
        return {}
    references = permissions.get("reference_diagrams")
    if not isinstance(references, list):
        return {}
    needed = reference_ids_needing_library(permissions)
    if not needed:
        return {}
    cache = get_diagram_cache()
    found: dict[str, str] = {}
    for item in references:
        if not isinstance(item, dict):
            continue
        diagram_id = str(item.get("id") or "").strip()
        if diagram_id not in needed or diagram_id in found:
            continue
        try:
            diagram = await cache.get_diagram(owner_id, diagram_id)
        except BACKGROUND_INFRA_ERRORS as exc:
            logger.warning(
                "[LearningSpace] Reference thumbnail unavailable owner=%s diagram=%s: %s",
                owner_id,
                diagram_id,
                exc,
            )
            continue
        if not diagram:
            continue
        thumb = diagram.get("thumbnail")
        if isinstance(thumb, str) and thumb.strip():
            found[diagram_id] = thumb
    return found


async def ensure_assignment_thumbnail_refs(
    db: AsyncSession,
    assignment: LearningAssignment,
    template_thumbnail: str | None,
) -> None:
    """Move legacy data-URL card images onto COS the first time an assignment is read."""
    raw = assignment.ai_permissions if isinstance(assignment.ai_permissions, dict) else {}
    if not assignment_thumbnail_promote_pending(raw, template_thumbnail):
        return
    library_thumbs: dict[str, str] = {}
    if reference_ids_needing_library(raw):
        library_thumbs = await reference_library_thumbnails(int(assignment.created_by), raw)
    prepared = await asyncio.to_thread(
        prepare_assignment_thumbnails_sync,
        raw,
        owner_id=int(assignment.created_by),
        template_thumbnail=template_thumbnail,
        reference_thumbnails=library_thumbs,
    )
    if not assignment_thumbnails_changed(raw, prepared):
        return
    assignment.ai_permissions = prepared
    try:
        await db.commit()
        await db.refresh(assignment)
    except DATABASE_ERRORS as exc:
        await db.rollback()
        logger.warning(
            "[LearningSpace] Thumbnail promote failed assignment=%s: %s",
            assignment.id,
            exc,
        )


async def ensure_submission_thumbnail_ref(
    db: AsyncSession,
    submission: LearningSubmission,
) -> None:
    """Move a submitted homework thumbnail onto COS when the snapshot still holds a data URL."""
    snap = submission.snapshot_spec
    if not isinstance(snap, dict):
        return
    updated = dict(snap)
    changed = await asyncio.to_thread(
        promote_snapshot_thumbnail_sync,
        updated,
        owner_id=int(submission.student_user_id),
    )
    if not changed:
        return
    submission.snapshot_spec = updated
    try:
        await db.commit()
        await db.refresh(submission)
    except DATABASE_ERRORS as exc:
        await db.rollback()
        logger.warning(
            "[LearningSpace] Submission thumbnail promote failed id=%s: %s",
            submission.id,
            exc,
        )
