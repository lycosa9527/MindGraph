"""Assignment open / submit / return helpers.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import User
from models.domain.diagrams import Diagram
from models.domain.learning_space import (
    ASSIGNMENT_STATUS_ACTIVE,
    SUBMISSION_STATUS_DRAFT,
    SUBMISSION_STATUS_RETURNED,
    SUBMISSION_STATUS_SUBMITTED,
    LearningAssignment,
    LearningSubmission,
)
from services.learning_space.access import assert_assignment_visible_to_learner
from services.learning_space.memberships import organization_info_map
from services.learning_space.blank_spec import (
    TEMPLATE_ROLE_SCAFFOLD,
    blank_spec_for_type,
    normalize_ls_diagram_type,
    resolve_template_role,
)
from services.learning_space.image_storage import (
    delete_stored_images_sync,
    public_instruction_images,
    ref_for_key,
    stored_image_keys,
)
from services.learning_space.passwords import merge_ai_permissions
from services.learning_space.thumbnail_promote import (
    ensure_assignment_thumbnail_refs,
    ensure_submission_thumbnail_ref,
)
from services.learning_space.thumbnail_storage import (
    TEMPLATE_THUMBNAIL_REF,
    assignment_thumbnail_src,
    collect_thumbnail_keys,
    display_thumbnail,
    present_reference_diagrams,
    promote_snapshot_thumbnail_sync,
    submission_thumbnail_src,
    submit_thumbnail_source,
    template_thumbnail_ref_ready,
)
from services.learning_space.students import count_class_students
from services.diagram.spec_coerce import coerce_diagram_spec
from services.redis.cache.redis_diagram_cache import get_diagram_cache
from services.utils.error_types import BACKGROUND_INFRA_ERRORS, DATABASE_ERRORS
from utils.db.session_open import system_rls_session

logger = logging.getLogger(__name__)


def effective_due_at(
    assignment: LearningAssignment,
    submission: LearningSubmission | None,
) -> datetime | None:
    """Per-student override wins over assignment due_at."""
    if submission is not None and submission.due_at_override is not None:
        return submission.due_at_override
    return assignment.due_at


def apply_learner_due(
    payload: dict[str, Any],
    assignment: LearningAssignment,
    submission: LearningSubmission | None,
) -> dict[str, Any]:
    """Show this student their own deadline, including a per-person extension."""
    due = effective_due_at(assignment, submission)
    payload["due_at"] = due.isoformat() if due is not None else None
    return payload


def submission_allows_resubmit(
    assignment: LearningAssignment,
    submission: LearningSubmission | None,
) -> bool:
    """True when a submitted work may be edited and submitted again."""
    if submission is None or submission.status != SUBMISSION_STATUS_SUBMITTED:
        return False
    if assignment.status != ASSIGNMENT_STATUS_ACTIVE:
        return False
    perms = merge_ai_permissions(assignment.ai_permissions if isinstance(assignment.ai_permissions, dict) else None)
    if not bool(perms.get("allow_resubmit", True)):
        return False
    due = effective_due_at(assignment, submission)
    if due is not None:
        due_aware = due if due.tzinfo else due.replace(tzinfo=UTC)
        if datetime.now(UTC) > due_aware:
            return bool(perms.get("allow_late_submit"))
    return True


def _clear_submission_review(submission: LearningSubmission) -> None:
    """Drop teacher review so resubmitted work returns to pending."""
    submission.review_scores = None
    submission.review_comment = None
    submission.review_liked = False
    submission.review_pinned = False
    submission.reviewed_at = None


def assert_can_edit_submission(
    assignment: LearningAssignment,
    submission: LearningSubmission | None,
) -> None:
    """Raise when past deadline or already submitted."""
    if assignment.status != ASSIGNMENT_STATUS_ACTIVE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Assignment closed")
    if submission is not None and submission.status == SUBMISSION_STATUS_SUBMITTED:
        if submission_allows_resubmit(assignment, submission):
            return
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Already submitted")
    due = effective_due_at(assignment, submission)
    if due is not None:
        due_aware = due if due.tzinfo else due.replace(tzinfo=UTC)
        if datetime.now(UTC) > due_aware:
            perms = merge_ai_permissions(
                assignment.ai_permissions if isinstance(assignment.ai_permissions, dict) else None
            )
            if not bool(perms.get("allow_late_submit")):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Past due")


async def get_assignment(db: AsyncSession, assignment_id: int) -> LearningAssignment:
    """Load assignment or 404."""
    result = await db.execute(select(LearningAssignment).where(LearningAssignment.id == assignment_id))
    assignment = result.scalar_one_or_none()
    if assignment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")
    return assignment


async def unreferenced_image_keys(
    db: AsyncSession,
    keys: list[str],
    *,
    except_assignment_id: int,
) -> list[str]:
    """Return COS/local keys that no other assignment still stores."""
    unused: list[str] = []
    for key in keys:
        ref = ref_for_key(key)
        result = await db.execute(
            select(LearningAssignment.id)
            .where(
                LearningAssignment.id != except_assignment_id,
                or_(
                    LearningAssignment.instruction_images.contains([ref]),
                    LearningAssignment.instruction_images.contains([key]),
                ),
            )
            .limit(1)
        )
        if result.scalar_one_or_none() is None:
            unused.append(key)
    return unused


async def delete_assignment(db: AsyncSession, assignment: LearningAssignment) -> None:
    """Delete an assignment and its submissions without relying on ORM cascade."""
    assignment_id = int(assignment.id)
    image_keys = stored_image_keys(assignment.instruction_images)
    snap_rows = await db.execute(
        select(LearningSubmission.snapshot_spec).where(LearningSubmission.assignment_id == assignment_id)
    )
    thumb_keys = collect_thumbnail_keys(
        assignment.ai_permissions,
        [row[0] for row in snap_rows.all()],
    )
    unused_keys = await unreferenced_image_keys(db, image_keys, except_assignment_id=assignment_id)
    unused_keys.extend(thumb_keys)
    class_id = int(assignment.class_id)
    try:
        await db.execute(delete(LearningSubmission).where(LearningSubmission.assignment_id == assignment_id))
        await db.execute(delete(LearningAssignment).where(LearningAssignment.id == assignment_id))
        await db.commit()
    except DATABASE_ERRORS as exc:
        await db.rollback()
        logger.error(
            "[LearningSpace] Delete assignment failed id=%s class=%s: %s",
            assignment_id,
            class_id,
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to delete assignment",
        ) from exc
    await asyncio.to_thread(delete_stored_images_sync, unused_keys)
    logger.info("[LearningSpace] Assignment deleted id=%s class=%s", assignment_id, class_id)


async def assert_homework_diagram_writable(
    db: AsyncSession,
    user_id: int,
    diagram_id: str,
) -> None:
    """Block canvas saves once the bound homework is submitted, closed, or past due."""
    cleaned = (diagram_id or "").strip()
    if not cleaned:
        return
    result = await db.execute(
        select(LearningSubmission).where(
            LearningSubmission.diagram_id == cleaned,
            LearningSubmission.student_user_id == user_id,
        )
    )
    for submission in result.scalars().all():
        assignment = await get_assignment(db, int(submission.assignment_id))
        assert_can_edit_submission(assignment, submission)


def student_homework_diagram_title(
    student_name: str | None,
    student_id: int,
    assignment_title: str,
) -> str:
    """Default canvas filename: 姓名_作业标题."""
    name = (student_name or "").strip() or str(student_id)
    asg = (assignment_title or "").strip() or "作业"
    title = f"{name}_{asg}"
    if len(title) > 200:
        return title[:197] + "..."
    return title


async def ensure_student_homework_diagram_title(
    student: User,
    assignment: LearningAssignment,
    diagram_id: str,
) -> None:
    """Keep an unsubmitted homework file named 姓名_作业标题 (best-effort)."""
    expected = student_homework_diagram_title(
        student.name if isinstance(student.name, str) else None,
        int(student.id),
        assignment.title,
    )
    cache = get_diagram_cache()
    try:
        existing = await cache.get_diagram(int(student.id), diagram_id)
    except BACKGROUND_INFRA_ERRORS:
        return
    if not existing:
        return
    current = str(existing.get("title") or "").strip()
    if current == expected:
        return
    thumb = existing.get("thumbnail")
    thumbnail = str(thumb) if isinstance(thumb, str) and thumb.strip() else None
    try:
        await cache.update_diagram_meta_only(
            int(student.id),
            diagram_id,
            expected,
            thumbnail,
        )
    except BACKGROUND_INFRA_ERRORS:
        return


def student_open_diagram_payload(
    assignment: LearningAssignment,
    template: dict[str, Any] | None,
) -> tuple[str, dict[str, Any], str, str | None]:
    """Diagram type, spec, language, thumbnail for a new student draft.

    Scaffold copies the teacher template. Reference / none start from a blank spec.
    """
    perms = merge_ai_permissions(assignment.ai_permissions if isinstance(assignment.ai_permissions, dict) else None)
    role = resolve_template_role(perms)
    if role == TEMPLATE_ROLE_SCAFFOLD:
        if not template or not isinstance(template.get("spec"), dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Template diagram not found",
            )
        dtype = normalize_ls_diagram_type(str(template.get("diagram_type") or "mind_map"))
        language = str(template.get("language") or "zh")
        thumb = template.get("thumbnail")
        thumbnail = str(thumb) if isinstance(thumb, str) and thumb.strip() else None
        return dtype, template["spec"], language, thumbnail

    dtype = normalize_ls_diagram_type(
        str(perms.get("diagram_type") or (template or {}).get("diagram_type") or "mind_map")
    )
    return dtype, blank_spec_for_type(assignment.title, dtype), "zh", None


async def _submission_after_insert_race(
    db: AsyncSession,
    assignment_id: int,
    student_id: int,
    *,
    detail: str,
) -> LearningSubmission:
    """Reload the winning row after a unique-constraint collision."""
    raced = await db.execute(
        select(LearningSubmission).where(
            LearningSubmission.assignment_id == assignment_id,
            LearningSubmission.student_user_id == student_id,
        )
    )
    existing = raced.scalar_one_or_none()
    if existing is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail) from None
    return existing


async def get_or_create_submission(
    db: AsyncSession,
    assignment: LearningAssignment,
    student: User,
    *,
    organization_id: int | None,
) -> LearningSubmission:
    """Ensure student has a draft submission with a start diagram."""
    assert_assignment_visible_to_learner(assignment)
    assignment_id = int(assignment.id)
    student_id = int(student.id)
    result = await db.execute(
        select(LearningSubmission).where(
            LearningSubmission.assignment_id == assignment_id,
            LearningSubmission.student_user_id == student_id,
        )
    )
    submission = result.scalar_one_or_none()
    if submission is not None and submission.diagram_id:
        if submission.status != SUBMISSION_STATUS_SUBMITTED:
            await ensure_student_homework_diagram_title(student, assignment, str(submission.diagram_id))
        return submission

    assert_can_edit_submission(assignment, submission)

    cache = get_diagram_cache()
    template: dict[str, Any] | None = None
    try:
        template = await cache.get_diagram(int(assignment.created_by), assignment.template_diagram_id)
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.warning(
            "[LearningSpace] Diagram service unavailable opening assignment=%s student=%s: %s",
            assignment_id,
            student_id,
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Diagram service unavailable",
        ) from exc

    diagram_type, spec, language, thumbnail = student_open_diagram_payload(assignment, template)

    title = student_homework_diagram_title(
        student.name if isinstance(student.name, str) else None,
        int(student.id),
        assignment.title,
    )
    try:
        save_ok, new_id, save_err = await cache.save_diagram(
            user_id=int(student.id),
            diagram_id=None,
            title=title,
            diagram_type=diagram_type,
            spec=spec,
            language=language,
            thumbnail=thumbnail,
            organization_id=organization_id,
        )
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.warning(
            "[LearningSpace] Diagram save unavailable assignment=%s student=%s: %s",
            assignment_id,
            student_id,
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Diagram service unavailable",
        ) from exc
    if not save_ok or not new_id:
        logger.warning(
            "[LearningSpace] Failed to create student diagram assignment=%s student=%s err=%s",
            assignment_id,
            student_id,
            save_err,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=save_err or "Failed to create student diagram",
        )

    if submission is None:
        org_id = int(assignment.organization_id) if assignment.organization_id else organization_id
        if org_id is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing organization")
        submission = LearningSubmission(
            assignment_id=assignment_id,
            student_user_id=student_id,
            organization_id=int(org_id),
            diagram_id=str(new_id),
            status=SUBMISSION_STATUS_DRAFT,
        )
        db.add(submission)
    else:
        submission.diagram_id = str(new_id)
        if submission.status == SUBMISSION_STATUS_RETURNED:
            submission.status = SUBMISSION_STATUS_DRAFT
    try:
        await db.commit()
        await db.refresh(submission)
    except IntegrityError:
        await db.rollback()
        logger.warning(
            "[LearningSpace] Open assignment raced assignment=%s student=%s",
            assignment_id,
            student_id,
        )
        return await _submission_after_insert_race(
            db,
            assignment_id,
            student_id,
            detail="Failed to create student diagram",
        )
    except DATABASE_ERRORS as exc:
        await db.rollback()
        logger.error(
            "[LearningSpace] Open assignment failed assignment=%s student=%s: %s",
            assignment_id,
            student_id,
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create student diagram",
        ) from exc
    logger.info(
        "[LearningSpace] Opened assignment=%s class=%s student=%s submission=%s diagram=%s",
        assignment_id,
        assignment.class_id,
        student_id,
        submission.id,
        submission.diagram_id,
    )
    return submission


async def bind_draft_diagram(
    db: AsyncSession,
    assignment: LearningAssignment,
    student: User,
    diagram_id: str,
) -> LearningSubmission:
    """Point the student's unsubmitted homework at a library diagram they own."""
    assert_assignment_visible_to_learner(assignment)
    assignment_id = int(assignment.id)
    student_id = int(student.id)
    diagram_id = (diagram_id or "").strip()
    if not diagram_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing diagram id")

    result = await db.execute(
        select(LearningSubmission).where(
            LearningSubmission.assignment_id == assignment_id,
            LearningSubmission.student_user_id == student_id,
        )
    )
    submission = result.scalar_one_or_none()
    assert_can_edit_submission(assignment, submission)
    if submission is not None and submission.diagram_id == diagram_id:
        await ensure_student_homework_diagram_title(student, assignment, diagram_id)
        return submission

    cache = get_diagram_cache()
    try:
        owned = await cache.get_diagram(int(student.id), diagram_id)
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.warning(
            "[LearningSpace] Diagram service unavailable binding assignment=%s student=%s: %s",
            assignment_id,
            student_id,
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Diagram service unavailable",
        ) from exc
    if not owned:
        logger.warning(
            "[LearningSpace] Bind draft diagram missing assignment=%s student=%s diagram=%s",
            assignment_id,
            student_id,
            diagram_id,
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Diagram not found")

    if submission is None:
        org_id = int(assignment.organization_id) if assignment.organization_id else None
        if org_id is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing organization")
        submission = LearningSubmission(
            assignment_id=assignment_id,
            student_user_id=student_id,
            organization_id=org_id,
            diagram_id=diagram_id,
            status=SUBMISSION_STATUS_DRAFT,
        )
        db.add(submission)
    else:
        submission.diagram_id = diagram_id
        if submission.status == SUBMISSION_STATUS_RETURNED:
            submission.status = SUBMISSION_STATUS_DRAFT
    try:
        await db.commit()
        await db.refresh(submission)
    except IntegrityError:
        await db.rollback()
        logger.warning(
            "[LearningSpace] Bind draft raced assignment=%s student=%s",
            assignment_id,
            student_id,
        )
        submission = await _submission_after_insert_race(
            db,
            assignment_id,
            student_id,
            detail="Failed to bind draft diagram",
        )
    except DATABASE_ERRORS as exc:
        await db.rollback()
        logger.error(
            "[LearningSpace] Bind draft failed assignment=%s student=%s: %s",
            assignment_id,
            student_id,
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to bind draft diagram",
        ) from exc
    await ensure_student_homework_diagram_title(student, assignment, diagram_id)
    logger.info(
        "[LearningSpace] Bound draft assignment=%s student=%s submission=%s diagram=%s",
        assignment_id,
        student_id,
        submission.id,
        diagram_id,
    )
    return submission


async def submit_assignment(
    db: AsyncSession,
    assignment: LearningAssignment,
    student: User,
) -> LearningSubmission:
    """Freeze snapshot and mark submitted."""
    assert_assignment_visible_to_learner(assignment)
    result = await db.execute(
        select(LearningSubmission).where(
            LearningSubmission.assignment_id == assignment.id,
            LearningSubmission.student_user_id == student.id,
        )
    )
    submission = result.scalar_one_or_none()
    if submission is None or not submission.diagram_id:
        logger.warning(
            "[LearningSpace] Submit without open draft assignment=%s student=%s",
            assignment.id,
            student.id,
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Open assignment first")
    assert_can_edit_submission(assignment, submission)

    cache = get_diagram_cache()
    try:
        diagram = await cache.get_diagram(int(student.id), submission.diagram_id)
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.warning(
            "[LearningSpace] Diagram service unavailable submitting assignment=%s student=%s: %s",
            assignment.id,
            student.id,
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Diagram service unavailable",
        ) from exc
    snapshot: dict[str, Any] | None = None
    previous_snap = submission.snapshot_spec if isinstance(submission.snapshot_spec, dict) else None
    previous_keys = collect_thumbnail_keys(None, [previous_snap] if previous_snap else [])
    if diagram:
        previous_thumb = previous_snap.get("thumbnail") if previous_snap else None
        snapshot = {
            "title": diagram.get("title"),
            "diagram_type": diagram.get("diagram_type"),
            "spec": diagram.get("spec"),
            "language": diagram.get("language", "zh"),
            "thumbnail": submit_thumbnail_source(diagram.get("thumbnail"), previous_thumb),
        }
        await asyncio.to_thread(
            promote_snapshot_thumbnail_sync,
            snapshot,
            owner_id=int(student.id),
        )
    else:
        logger.warning(
            "[LearningSpace] Submit without live diagram assignment=%s student=%s diagram=%s",
            assignment.id,
            student.id,
            submission.diagram_id,
        )
    resubmitting = submission.status == SUBMISSION_STATUS_SUBMITTED
    if resubmitting:
        _clear_submission_review(submission)
    submission.snapshot_spec = snapshot
    submission.status = SUBMISSION_STATUS_SUBMITTED
    submission.submitted_at = datetime.now(UTC)
    try:
        await db.commit()
        await db.refresh(submission)
    except DATABASE_ERRORS as exc:
        await db.rollback()
        fresh_keys = collect_thumbnail_keys(None, [snapshot] if isinstance(snapshot, dict) else [])
        orphans = [key for key in fresh_keys if key not in previous_keys]
        if orphans:
            await asyncio.to_thread(delete_stored_images_sync, orphans)
        logger.error(
            "[LearningSpace] Submit failed assignment=%s student=%s: %s",
            assignment.id,
            student.id,
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit assignment",
        ) from exc
    fresh_keys = collect_thumbnail_keys(None, [snapshot] if isinstance(snapshot, dict) else [])
    stale_keys = [key for key in previous_keys if key not in fresh_keys]
    if stale_keys:
        await asyncio.to_thread(delete_stored_images_sync, stale_keys)
    logger.info(
        "[LearningSpace] Submitted assignment=%s class=%s student=%s submission=%s",
        assignment.id,
        assignment.class_id,
        student.id,
        submission.id,
    )
    return submission


async def return_submission(
    db: AsyncSession,
    submission: LearningSubmission,
) -> LearningSubmission:
    """Teacher returns submitted work for revision."""
    if submission.status != SUBMISSION_STATUS_SUBMITTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only submitted work can be returned",
        )
    submission.status = SUBMISSION_STATUS_RETURNED
    submission.submitted_at = None
    try:
        await db.commit()
        await db.refresh(submission)
    except DATABASE_ERRORS as exc:
        await db.rollback()
        logger.error(
            "[LearningSpace] Return submission failed id=%s assignment=%s: %s",
            submission.id,
            submission.assignment_id,
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to return submission",
        ) from exc
    logger.info(
        "[LearningSpace] Returned submission=%s assignment=%s student=%s",
        submission.id,
        submission.assignment_id,
        submission.student_user_id,
    )
    return submission


async def extend_submission_due(
    db: AsyncSession,
    submission: LearningSubmission,
    due_at: datetime,
) -> LearningSubmission:
    """Set one student's deadline. The new time must be in the future."""
    due = due_at if due_at.tzinfo is not None else due_at.replace(tzinfo=UTC)
    if due <= datetime.now(UTC):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Due date must be in the future",
        )
    submission.due_at_override = due
    try:
        await db.commit()
        await db.refresh(submission)
    except DATABASE_ERRORS as exc:
        await db.rollback()
        logger.error(
            "[LearningSpace] Extend due failed submission=%s: %s",
            submission.id,
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to extend due date",
        ) from exc
    logger.info(
        "[LearningSpace] Extended due submission=%s assignment=%s",
        submission.id,
        submission.assignment_id,
    )
    return submission


def _public_ai_permissions(assignment: LearningAssignment) -> dict[str, Any]:
    """Permissions for clients: thumbnail bytes stay on COS, img src is a download hop."""
    raw = assignment.ai_permissions if isinstance(assignment.ai_permissions, dict) else None
    merged = merge_ai_permissions(raw)
    merged.pop(TEMPLATE_THUMBNAIL_REF, None)
    references = merged.get("reference_diagrams")
    if isinstance(references, list) and assignment.id is not None:
        merged["reference_diagrams"] = present_reference_diagrams(
            references,
            assignment_id=int(assignment.id),
        )
    return merged


def assignment_public_dict(
    assignment: LearningAssignment,
    *,
    template_thumbnail: str | None = None,
    submission_count: int | None = None,
    submitted_count: int | None = None,
    student_count: int | None = None,
) -> dict[str, Any]:
    """Serialize assignment for API responses."""
    payload: dict[str, Any] = {
        "id": assignment.id,
        "class_id": assignment.class_id,
        "title": assignment.title,
        "instructions": assignment.instructions,
        "instruction_images": public_instruction_images(
            assignment.instruction_images,
            assignment_id=int(assignment.id) if assignment.id is not None else None,
        ),
        "template_diagram_id": assignment.template_diagram_id,
        "due_at": assignment.due_at.isoformat() if assignment.due_at else None,
        "ai_permissions": _public_ai_permissions(assignment),
        "status": assignment.status,
        "created_by": assignment.created_by,
        "created_at": assignment.created_at.isoformat() if assignment.created_at else None,
    }
    if template_thumbnail is not None:
        payload["template_thumbnail"] = template_thumbnail
    elif assignment.id is not None:
        raw_perms = assignment.ai_permissions if isinstance(assignment.ai_permissions, dict) else None
        stored_ref = raw_perms.get(TEMPLATE_THUMBNAIL_REF) if isinstance(raw_perms, dict) else None
        shown = display_thumbnail(stored_ref, assignment_thumbnail_src(int(assignment.id)))
        if shown:
            payload["template_thumbnail"] = shown
    if submission_count is not None:
        payload["submission_count"] = submission_count
    if submitted_count is not None:
        payload["submitted_count"] = submitted_count
    if student_count is not None:
        payload["student_count"] = student_count
    return payload


def _normalize_preview_spec(spec: Any) -> dict[str, Any] | None:
    """Unwrap saved diagram JSON to the semantic spec Showcase preview expects."""
    if not isinstance(spec, dict):
        return None
    candidate: dict[str, Any] = spec
    nested = spec.get("spec")
    if isinstance(nested, dict) and (
        nested.get("type") or nested.get("topic") or nested.get("data") or nested.get("nodes") or nested.get("children")
    ):
        candidate = nested
    if (
        candidate.get("type")
        or candidate.get("topic")
        or candidate.get("data")
        or candidate.get("nodes")
        or candidate.get("children")
        or candidate.get("context")
        or candidate.get("attributes")
        or candidate.get("whole")
        or candidate.get("event")
    ):
        return candidate
    return None


def _resolve_submission_org_id(
    student: User | None,
    submission: LearningSubmission,
) -> int | None:
    """Prefer user org; fall back to submission row org (always set for homework)."""
    if student is not None:
        user_org = getattr(student, "organization_id", None)
        if user_org is not None:
            return int(user_org)
    sub_org = getattr(submission, "organization_id", None)
    if sub_org is not None:
        return int(sub_org)
    return None


async def _load_submission_diagram(
    submission: LearningSubmission,
    _student: User | None,
) -> dict[str, Any] | None:
    """Load a student's homework diagram for staff/class-wall preview."""
    diagram_id = str(submission.diagram_id or "").strip()
    if not diagram_id:
        return None
    student_id = int(submission.student_user_id)
    cache = get_diagram_cache()
    try:
        cached = await cache.get_diagram(student_id, diagram_id)
    except BACKGROUND_INFRA_ERRORS:
        cached = None
    if isinstance(cached, dict):
        spec = _normalize_preview_spec(cached.get("spec"))
        if spec is not None:
            return cached

    try:
        async with system_rls_session() as sys_db:
            result = await sys_db.execute(
                select(Diagram).where(
                    Diagram.id == diagram_id,
                    Diagram.user_id == student_id,
                    Diagram.is_deleted.is_(False),
                )
            )
            row = result.scalar_one_or_none()
            if row is None:
                return None
            spec = _normalize_preview_spec(coerce_diagram_spec(getattr(row, "spec", None)))
            if spec is None:
                return None
            return {
                "title": getattr(row, "title", "") or "",
                "diagram_type": getattr(row, "diagram_type", "") or "mind_map",
                "spec": spec,
                "language": getattr(row, "language", "zh") or "zh",
                "thumbnail": getattr(row, "thumbnail", None),
            }
    except DATABASE_ERRORS as exc:
        logger.warning(
            "[LearningSpace] System diagram load failed submission=%s diagram=%s: %s",
            submission.id,
            diagram_id,
            exc,
        )
        return None


def _resolve_submission_diagram_fields(
    submission: LearningSubmission,
    diagram: dict[str, Any] | None,
) -> tuple[str | None, dict[str, Any] | None, str, str]:
    """Thumbnail plus preview spec/type/title from snapshot or live diagram."""
    diagram_thumbnail: str | None = None
    preview_spec: dict[str, Any] | None = None
    preview_diagram_type = "mind_map"
    preview_title = ""

    snap = submission.snapshot_spec if isinstance(submission.snapshot_spec, dict) else None
    snap_spec = snap.get("spec") if snap else None
    if snap:
        snap_thumb = snap.get("thumbnail")
        if isinstance(snap_thumb, str) and snap_thumb.strip():
            diagram_thumbnail = snap_thumb
    if not diagram_thumbnail and diagram:
        thumb = diagram.get("thumbnail")
        if isinstance(thumb, str) and thumb.strip():
            diagram_thumbnail = thumb

    if snap:
        preview_spec = _normalize_preview_spec(snap_spec)
        if snap.get("diagram_type"):
            preview_diagram_type = str(snap.get("diagram_type") or preview_diagram_type)
        if snap.get("title"):
            preview_title = str(snap.get("title") or preview_title)
    # A backfilled card may store only the COS thumbnail. A frozen spec still wins.
    if preview_spec is None and diagram is not None and not isinstance(snap_spec, dict):
        preview_spec = _normalize_preview_spec(diagram.get("spec"))
        preview_diagram_type = str(diagram.get("diagram_type") or preview_diagram_type)
        if not preview_title:
            preview_title = str(diagram.get("title") or "")

    return diagram_thumbnail, preview_spec, preview_diagram_type, preview_title


def submission_public_dict(
    submission: LearningSubmission,
    *,
    student_name: str | None = None,
    organization_name: str | None = None,
    diagram_thumbnail: str | None = None,
    include_preview: bool = False,
    assignment_title: str | None = None,
    preview_spec: dict[str, Any] | None = None,
    preview_diagram_type: str | None = None,
    preview_title: str | None = None,
) -> dict[str, Any]:
    """Serialize submission for API responses."""
    payload: dict[str, Any] = {
        "id": submission.id,
        "assignment_id": submission.assignment_id,
        "student_user_id": submission.student_user_id,
        "diagram_id": submission.diagram_id,
        "status": submission.status,
        "submitted_at": submission.submitted_at.isoformat() if submission.submitted_at else None,
        "due_at_override": submission.due_at_override.isoformat() if submission.due_at_override else None,
        "review_liked": bool(getattr(submission, "review_liked", False)),
        "review_pinned": bool(getattr(submission, "review_pinned", False)),
        "reviewed_at": (submission.reviewed_at.isoformat() if isinstance(submission.reviewed_at, datetime) else None),
    }
    scores = getattr(submission, "review_scores", None)
    if isinstance(scores, dict):
        payload["review_scores"] = {str(k): int(v) if isinstance(v, (int, float)) else 0 for k, v in scores.items()}
    else:
        payload["review_scores"] = None
    comment = getattr(submission, "review_comment", None)
    payload["review_comment"] = comment if isinstance(comment, str) else None
    if student_name is not None:
        payload["student_name"] = student_name
    if organization_name is not None:
        payload["organization_name"] = organization_name
    if diagram_thumbnail is not None:
        payload["diagram_thumbnail"] = diagram_thumbnail
    if assignment_title is not None:
        payload["assignment_title"] = assignment_title
    if include_preview:
        payload["preview_spec"] = preview_spec if isinstance(preview_spec, dict) else None
        payload["preview_diagram_type"] = str(preview_diagram_type or "mind_map")
        payload["preview_title"] = str(preview_title or "")
    return payload


async def enrich_submission_dict(
    db: AsyncSession,
    submission: LearningSubmission,
    *,
    include_preview: bool = False,
    assignment_title: str | None = None,
) -> dict[str, Any]:
    """Submission payload with student name, org label, thumbnail, optional preview spec."""
    student = await db.get(User, int(submission.student_user_id))
    student_name = (student.name or "").strip() if student is not None else ""
    organization_name = ""
    org_id = _resolve_submission_org_id(student, submission)
    if org_id is not None:
        org_info = await organization_info_map({org_id})
        organization_name = str(org_info.get(org_id, {}).get("organization_name") or "")

    diagram: dict[str, Any] | None = None
    if submission.diagram_id:
        diagram = await _load_submission_diagram(submission, student)

    await ensure_submission_thumbnail_ref(db, submission)
    diagram_thumbnail, preview_spec, preview_diagram_type, preview_title = _resolve_submission_diagram_fields(
        submission,
        diagram,
    )
    if submission.id is not None:
        shown = display_thumbnail(diagram_thumbnail, submission_thumbnail_src(int(submission.id)))
        if shown:
            diagram_thumbnail = shown
    return submission_public_dict(
        submission,
        student_name=student_name or f"#{submission.student_user_id}",
        organization_name=organization_name or None,
        diagram_thumbnail=diagram_thumbnail,
        include_preview=include_preview,
        assignment_title=assignment_title,
        preview_spec=preview_spec if include_preview else None,
        preview_diagram_type=preview_diagram_type if include_preview else None,
        preview_title=preview_title if include_preview else None,
    )


async def enrich_assignment_dict(
    db: AsyncSession,
    assignment: LearningAssignment,
) -> dict[str, Any]:
    """Assignment payload with template thumbnail and submission counts."""
    template_thumbnail: str | None = None
    raw_perms = assignment.ai_permissions if isinstance(assignment.ai_permissions, dict) else {}
    live_thumb: str | None = None
    if not template_thumbnail_ref_ready(raw_perms):
        cache = get_diagram_cache()
        try:
            template = await cache.get_diagram(int(assignment.created_by), assignment.template_diagram_id)
            if template:
                thumb = template.get("thumbnail")
                if isinstance(thumb, str) and thumb.strip():
                    live_thumb = thumb
        except BACKGROUND_INFRA_ERRORS:
            live_thumb = None
    await ensure_assignment_thumbnail_refs(db, assignment, live_thumb)
    if assignment.id is not None:
        raw_perms = assignment.ai_permissions if isinstance(assignment.ai_permissions, dict) else None
        stored_ref = raw_perms.get(TEMPLATE_THUMBNAIL_REF) if isinstance(raw_perms, dict) else None
        template_thumbnail = display_thumbnail(stored_ref, assignment_thumbnail_src(int(assignment.id)))
    if template_thumbnail is None:
        template_thumbnail = display_thumbnail(live_thumb, "")

    total = await db.execute(
        select(func.count()).select_from(LearningSubmission).where(LearningSubmission.assignment_id == assignment.id)
    )
    submitted = await db.execute(
        select(func.count())
        .select_from(LearningSubmission)
        .where(
            LearningSubmission.assignment_id == assignment.id,
            LearningSubmission.status == SUBMISSION_STATUS_SUBMITTED,
        )
    )
    roster = await count_class_students(db, int(assignment.class_id))
    return assignment_public_dict(
        assignment,
        template_thumbnail=template_thumbnail,
        submission_count=int(total.scalar_one() or 0),
        submitted_count=int(submitted.scalar_one() or 0),
        student_count=roster,
    )


async def load_template_preview(
    assignment: LearningAssignment,
) -> dict[str, Any]:
    """Return template diagram preview fields for requirements UI."""
    cache = get_diagram_cache()
    try:
        template = await cache.get_diagram(int(assignment.created_by), assignment.template_diagram_id)
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.warning(
            "[LearningSpace] Template preview unavailable assignment=%s: %s",
            assignment.id,
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Diagram service unavailable",
        ) from exc
    if not template:
        logger.warning(
            "[LearningSpace] Template diagram missing assignment=%s template=%s",
            assignment.id,
            assignment.template_diagram_id,
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template diagram not found")
    spec = template.get("spec")
    raw_perms = assignment.ai_permissions if isinstance(assignment.ai_permissions, dict) else None
    stored_ref = raw_perms.get(TEMPLATE_THUMBNAIL_REF) if isinstance(raw_perms, dict) else None
    thumb_out = None
    if assignment.id is not None:
        thumb_out = display_thumbnail(stored_ref, assignment_thumbnail_src(int(assignment.id)))
    if thumb_out is None:
        thumb_out = display_thumbnail(template.get("thumbnail"), "")
    return {
        "template_diagram_id": assignment.template_diagram_id,
        "title": str(template.get("title") or assignment.title),
        "diagram_type": str(template.get("diagram_type") or "mind_map"),
        "language": str(template.get("language") or "zh"),
        "preview_spec": spec if isinstance(spec, dict) else None,
        "thumbnail": thumb_out,
    }


async def save_submission_review(
    db: AsyncSession,
    submission: LearningSubmission,
    *,
    scores: dict[str, Any],
    comment: str,
    liked: bool,
    pinned: bool,
) -> LearningSubmission:
    """Persist teacher review on a submission."""
    cleaned_scores: dict[str, int] = {}
    for key, value in scores.items():
        label = str(key).strip()
        if not label:
            continue
        try:
            stars = int(value)
        except (TypeError, ValueError):
            stars = 0
        cleaned_scores[label] = max(0, min(5, stars))
    submission.review_scores = cleaned_scores
    submission.review_comment = (comment or "").strip()[:4000] or None
    submission.review_liked = bool(liked)
    submission.review_pinned = bool(pinned)
    submission.reviewed_at = datetime.now(UTC)
    try:
        await db.commit()
        await db.refresh(submission)
    except DATABASE_ERRORS as exc:
        await db.rollback()
        logger.error(
            "[LearningSpace] Review save failed submission=%s assignment=%s: %s",
            submission.id,
            submission.assignment_id,
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save review",
        ) from exc
    logger.info(
        "[LearningSpace] Reviewed submission=%s assignment=%s student=%s liked=%s pinned=%s",
        submission.id,
        submission.assignment_id,
        submission.student_user_id,
        liked,
        pinned,
    )
    return submission
