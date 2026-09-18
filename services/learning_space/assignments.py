"""Assignment open / submit / return helpers.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import User
from models.domain.learning_space import (
    ASSIGNMENT_STATUS_ACTIVE,
    SUBMISSION_STATUS_DRAFT,
    SUBMISSION_STATUS_RETURNED,
    SUBMISSION_STATUS_SUBMITTED,
    LearningAssignment,
    LearningSubmission,
)
from services.learning_space.blank_spec import (
    TEMPLATE_ROLE_SCAFFOLD,
    blank_spec_for_type,
    normalize_ls_diagram_type,
    resolve_template_role,
)
from services.learning_space.passwords import merge_ai_permissions
from services.learning_space.students import count_class_students
from services.redis.cache.redis_diagram_cache import get_diagram_cache
from services.utils.error_types import BACKGROUND_INFRA_ERRORS, DATABASE_ERRORS


def effective_due_at(
    assignment: LearningAssignment,
    submission: LearningSubmission | None,
) -> datetime | None:
    """Per-student override wins over assignment due_at."""
    if submission is not None and submission.due_at_override is not None:
        return submission.due_at_override
    return assignment.due_at


def assert_can_edit_submission(
    assignment: LearningAssignment,
    submission: LearningSubmission | None,
) -> None:
    """Raise when past deadline or already submitted."""
    if assignment.status != ASSIGNMENT_STATUS_ACTIVE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Assignment closed")
    if submission is not None and submission.status == SUBMISSION_STATUS_SUBMITTED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Already submitted")
    due = effective_due_at(assignment, submission)
    if due is not None:
        due_aware = due if due.tzinfo else due.replace(tzinfo=UTC)
        if datetime.now(UTC) > due_aware:
            perms = assignment.ai_permissions if isinstance(assignment.ai_permissions, dict) else {}
            if not bool(perms.get("allow_late_submit")):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Past due")


async def get_assignment(db: AsyncSession, assignment_id: int) -> LearningAssignment:
    """Load assignment or 404."""
    result = await db.execute(select(LearningAssignment).where(LearningAssignment.id == assignment_id))
    assignment = result.scalar_one_or_none()
    if assignment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")
    return assignment


async def delete_assignment(db: AsyncSession, assignment: LearningAssignment) -> None:
    """Delete an assignment and its submissions without relying on ORM cascade."""
    assignment_id = int(assignment.id)
    try:
        await db.execute(delete(LearningSubmission).where(LearningSubmission.assignment_id == assignment_id))
        await db.execute(delete(LearningAssignment).where(LearningAssignment.id == assignment_id))
        await db.commit()
    except DATABASE_ERRORS as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to delete assignment",
        ) from exc


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


async def get_or_create_submission(
    db: AsyncSession,
    assignment: LearningAssignment,
    student: User,
    *,
    organization_id: int | None,
) -> LearningSubmission:
    """Ensure student has a draft submission with a start diagram."""
    result = await db.execute(
        select(LearningSubmission).where(
            LearningSubmission.assignment_id == assignment.id,
            LearningSubmission.student_user_id == student.id,
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
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Diagram service unavailable",
        ) from exc
    if not save_ok or not new_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=save_err or "Failed to create student diagram",
        )

    if submission is None:
        submission = LearningSubmission(
            assignment_id=assignment.id,
            student_user_id=int(student.id),
            diagram_id=str(new_id),
            status=SUBMISSION_STATUS_DRAFT,
        )
        db.add(submission)
    else:
        submission.diagram_id = str(new_id)
        if submission.status == SUBMISSION_STATUS_RETURNED:
            submission.status = SUBMISSION_STATUS_DRAFT
    await db.commit()
    await db.refresh(submission)
    return submission


async def bind_draft_diagram(
    db: AsyncSession,
    assignment: LearningAssignment,
    student: User,
    diagram_id: str,
) -> LearningSubmission:
    """Point the student's unsubmitted homework at a library diagram they own."""
    diagram_id = (diagram_id or "").strip()
    if not diagram_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing diagram id")

    result = await db.execute(
        select(LearningSubmission).where(
            LearningSubmission.assignment_id == assignment.id,
            LearningSubmission.student_user_id == student.id,
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
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Diagram service unavailable",
        ) from exc
    if not owned:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Diagram not found")

    if submission is None:
        submission = LearningSubmission(
            assignment_id=assignment.id,
            student_user_id=int(student.id),
            diagram_id=diagram_id,
            status=SUBMISSION_STATUS_DRAFT,
        )
        db.add(submission)
    else:
        submission.diagram_id = diagram_id
        if submission.status == SUBMISSION_STATUS_RETURNED:
            submission.status = SUBMISSION_STATUS_DRAFT
    await db.commit()
    await db.refresh(submission)
    await ensure_student_homework_diagram_title(student, assignment, diagram_id)
    return submission


async def submit_assignment(
    db: AsyncSession,
    assignment: LearningAssignment,
    student: User,
) -> LearningSubmission:
    """Freeze snapshot and mark submitted."""
    result = await db.execute(
        select(LearningSubmission).where(
            LearningSubmission.assignment_id == assignment.id,
            LearningSubmission.student_user_id == student.id,
        )
    )
    submission = result.scalar_one_or_none()
    if submission is None or not submission.diagram_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Open assignment first")
    assert_can_edit_submission(assignment, submission)

    cache = get_diagram_cache()
    diagram = await cache.get_diagram(int(student.id), submission.diagram_id)
    snapshot: dict[str, Any] | None = None
    if diagram:
        snapshot = {
            "title": diagram.get("title"),
            "diagram_type": diagram.get("diagram_type"),
            "spec": diagram.get("spec"),
            "language": diagram.get("language", "zh"),
            "thumbnail": diagram.get("thumbnail"),
        }
    submission.snapshot_spec = snapshot
    submission.status = SUBMISSION_STATUS_SUBMITTED
    submission.submitted_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(submission)
    return submission


async def return_submission(
    db: AsyncSession,
    submission: LearningSubmission,
) -> LearningSubmission:
    """Teacher returns work for revision."""
    submission.status = SUBMISSION_STATUS_RETURNED
    submission.submitted_at = None
    await db.commit()
    await db.refresh(submission)
    return submission


def assignment_public_dict(
    assignment: LearningAssignment,
    *,
    template_thumbnail: str | None = None,
    submission_count: int | None = None,
    submitted_count: int | None = None,
    student_count: int | None = None,
) -> dict[str, Any]:
    """Serialize assignment for API responses."""
    images = assignment.instruction_images
    if not isinstance(images, list):
        images = []
    payload: dict[str, Any] = {
        "id": assignment.id,
        "class_id": assignment.class_id,
        "title": assignment.title,
        "instructions": assignment.instructions,
        "instruction_images": [str(u) for u in images if isinstance(u, str) and u.strip()][:6],
        "template_diagram_id": assignment.template_diagram_id,
        "due_at": assignment.due_at.isoformat() if assignment.due_at else None,
        "ai_permissions": merge_ai_permissions(
            assignment.ai_permissions if isinstance(assignment.ai_permissions, dict) else None
        ),
        "status": assignment.status,
        "created_by": assignment.created_by,
        "created_at": assignment.created_at.isoformat() if assignment.created_at else None,
    }
    if template_thumbnail is not None:
        payload["template_thumbnail"] = template_thumbnail
    if submission_count is not None:
        payload["submission_count"] = submission_count
    if submitted_count is not None:
        payload["submitted_count"] = submitted_count
    if student_count is not None:
        payload["student_count"] = student_count
    return payload


def submission_public_dict(
    submission: LearningSubmission,
    *,
    student_name: str | None = None,
    diagram_thumbnail: str | None = None,
    include_preview: bool = False,
    assignment_title: str | None = None,
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
    if diagram_thumbnail is not None:
        payload["diagram_thumbnail"] = diagram_thumbnail
    if assignment_title is not None:
        payload["assignment_title"] = assignment_title
    if include_preview:
        snap = submission.snapshot_spec if isinstance(submission.snapshot_spec, dict) else None
        preview_spec = snap.get("spec") if snap else None
        payload["preview_spec"] = preview_spec if isinstance(preview_spec, dict) else None
        payload["preview_diagram_type"] = str(snap.get("diagram_type") or "mind_map") if snap else "mind_map"
        payload["preview_title"] = str(snap.get("title") or "") if snap else ""
    return payload


async def enrich_submission_dict(
    db: AsyncSession,
    submission: LearningSubmission,
    *,
    include_preview: bool = False,
    assignment_title: str | None = None,
) -> dict[str, Any]:
    """Submission payload with student name and diagram thumbnail."""
    student = await db.get(User, int(submission.student_user_id))
    student_name = (student.name or "").strip() if student is not None else ""
    diagram_thumbnail: str | None = None
    if submission.diagram_id:
        cache = get_diagram_cache()
        try:
            diagram = await cache.get_diagram(int(submission.student_user_id), str(submission.diagram_id))
            if diagram:
                thumb = diagram.get("thumbnail")
                if isinstance(thumb, str) and thumb.strip():
                    diagram_thumbnail = thumb
        except BACKGROUND_INFRA_ERRORS:
            diagram_thumbnail = None
    if not diagram_thumbnail and isinstance(submission.snapshot_spec, dict):
        # Snapshot may carry thumbnail if older clients stored it; prefer live above.
        snap_thumb = submission.snapshot_spec.get("thumbnail")
        if isinstance(snap_thumb, str) and snap_thumb.strip():
            diagram_thumbnail = snap_thumb
    return submission_public_dict(
        submission,
        student_name=student_name or f"#{submission.student_user_id}",
        diagram_thumbnail=diagram_thumbnail,
        include_preview=include_preview,
        assignment_title=assignment_title,
    )


async def enrich_assignment_dict(
    db: AsyncSession,
    assignment: LearningAssignment,
) -> dict[str, Any]:
    """Assignment payload with template thumbnail and submission counts."""
    template_thumbnail: str | None = None
    cache = get_diagram_cache()
    try:
        template = await cache.get_diagram(int(assignment.created_by), assignment.template_diagram_id)
        if template:
            thumb = template.get("thumbnail")
            if isinstance(thumb, str) and thumb.strip():
                template_thumbnail = thumb
    except BACKGROUND_INFRA_ERRORS:
        template_thumbnail = None

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
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Diagram service unavailable",
        ) from exc
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template diagram not found")
    spec = template.get("spec")
    thumb = template.get("thumbnail")
    return {
        "template_diagram_id": assignment.template_diagram_id,
        "title": str(template.get("title") or assignment.title),
        "diagram_type": str(template.get("diagram_type") or "mind_map"),
        "language": str(template.get("language") or "zh"),
        "preview_spec": spec if isinstance(spec, dict) else None,
        "thumbnail": thumb if isinstance(thumb, str) and thumb.strip() else None,
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save review",
        ) from exc
    return submission
