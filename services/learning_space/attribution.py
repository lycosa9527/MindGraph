"""Publisher and grader names for Learning Space homework cards.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.learning_space import LearningSubmission
from services.learning_space.assignments import author_names_for_user_ids, submission_public_dict
from services.learning_space.review_mark import submission_has_review


async def review_marks_by_assignment(
    db: AsyncSession,
    assignment_ids: list[int],
) -> dict[int, tuple[list[int], bool]]:
    """Graders per assignment, plus whether an older review has no grader id."""
    if not assignment_ids:
        return {}
    result = await db.execute(
        select(LearningSubmission.assignment_id, LearningSubmission.reviewed_by).where(
            LearningSubmission.assignment_id.in_(tuple(assignment_ids)),
            submission_has_review(),
        )
    )
    grouped: dict[int, set[int]] = {}
    unnamed: dict[int, bool] = {}
    for assignment_id, reviewer_id in result.all():
        key = int(assignment_id)
        grouped.setdefault(key, set())
        unnamed.setdefault(key, False)
        if reviewer_id is None:
            unnamed[key] = True
            continue
        grouped[key].add(int(reviewer_id))
    return {key: (sorted(ids), unnamed[key]) for key, ids in grouped.items()}


def submission_label_user_ids(submissions: list[LearningSubmission]) -> set[int]:
    """Author and grader ids already stored on submissions the caller can read."""
    ids: set[int] = set()
    for row in submissions:
        ids.add(int(row.student_user_id))
        reviewer_id = row.reviewed_by
        if isinstance(reviewer_id, int):
            ids.add(reviewer_id)
    return ids


def _name_or_blank(names: dict[int, str], user_id: int) -> str:
    return (names.get(user_id) or "").strip()


def assignment_grader_labels(
    grader_ids: list[int],
    unnamed: bool,
    names: dict[int, str],
) -> tuple[list[str], bool]:
    """Names to show, and whether any graded row still has no display name."""
    labels: list[str] = []
    missing_name = False
    for reviewer_id in grader_ids:
        label = _name_or_blank(names, reviewer_id)
        if label:
            labels.append(label)
        else:
            missing_name = True
    return labels, unnamed or missing_name


async def attach_assignment_people(db: AsyncSession, items: list[dict[str, Any]]) -> None:
    """Fill created_by_name, reviewer_names, and a nested submission's reviewer_name."""
    if not items:
        return
    assignment_ids = [int(row["id"]) for row in items if isinstance(row.get("id"), int)]
    marks = await review_marks_by_assignment(db, assignment_ids)
    user_ids: set[int] = set()
    for row in items:
        created_by = row.get("created_by")
        if isinstance(created_by, int):
            user_ids.add(created_by)
        assignment_id = row.get("id")
        if isinstance(assignment_id, int):
            grader_ids, _unnamed = marks.get(assignment_id, ([], False))
            user_ids.update(grader_ids)
        submission = row.get("submission")
        if isinstance(submission, dict) and isinstance(submission.get("reviewed_by"), int):
            user_ids.add(int(submission["reviewed_by"]))
    names = await author_names_for_user_ids(user_ids)
    for row in items:
        created_by = row.get("created_by")
        if isinstance(created_by, int):
            row["created_by_name"] = _name_or_blank(names, created_by)
        assignment_id = row.get("id")
        if isinstance(assignment_id, int):
            grader_ids, unnamed = marks.get(assignment_id, ([], False))
        else:
            grader_ids, unnamed = [], False
        labels, row["has_unnamed_review"] = assignment_grader_labels(grader_ids, unnamed, names)
        row["reviewer_names"] = labels
        submission = row.get("submission")
        if isinstance(submission, dict):
            _attach_reviewer_name(submission, names)


async def named_submission_dict(submission: LearningSubmission, **kwargs: Any) -> dict[str, Any]:
    """One submission response, with reviewer_name taken from reviewed_by."""
    payload = submission_public_dict(submission, **kwargs)
    await attach_submission_reviewers([payload])
    return payload


async def attach_submission_reviewers(
    items: list[dict[str, Any]],
    names: dict[int, str] | None = None,
) -> None:
    """Fill reviewer_name on submission payloads from reviewed_by.

    Pass ``names`` when those user ids were already resolved with the authors.
    """
    if not items:
        return
    if names is None:
        user_ids = {int(row["reviewed_by"]) for row in items if isinstance(row.get("reviewed_by"), int)}
        names = await author_names_for_user_ids(user_ids)
    for row in items:
        _attach_reviewer_name(row, names)


def _attach_reviewer_name(row: dict[str, Any], names: dict[int, str]) -> None:
    reviewer_id = row.get("reviewed_by")
    if isinstance(reviewer_id, int):
        row["reviewer_name"] = _name_or_blank(names, reviewer_id)
        return
    row["reviewer_name"] = None
