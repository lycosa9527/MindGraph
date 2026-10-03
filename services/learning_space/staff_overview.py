"""Batched Learning Space staff overview queries.

Dashboard numbers must not load a diagram or instruction body per assignment.
Superadmins see every class, so per-row enrichment would time out.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import User
from models.domain.learning_space import (
    MEMBERSHIP_ROLE_LEARNER,
    SUBMISSION_STATUS_SUBMITTED,
    LearningAssignment,
    LearningClassMembership,
    LearningSubmission,
)
from utils.auth.role_constants import ROLE_STUDENT


async def roster_counts_by_class(db: AsyncSession, class_ids: list[int]) -> dict[int, int]:
    """Classroom students plus enrolled learners, one pair of grouped counts."""
    counts = {int(class_id): 0 for class_id in class_ids}
    if not counts:
        return counts
    ids = tuple(counts)
    classroom = await db.execute(
        select(User.learning_class_id, func.count())
        .where(User.learning_class_id.in_(ids), User.role == ROLE_STUDENT)
        .group_by(User.learning_class_id)
    )
    for class_id, total in classroom.all():
        if class_id is not None:
            counts[int(class_id)] = counts.get(int(class_id), 0) + int(total or 0)
    learners = await db.execute(
        select(LearningClassMembership.class_id, func.count())
        .where(
            LearningClassMembership.class_id.in_(ids),
            LearningClassMembership.role == MEMBERSHIP_ROLE_LEARNER,
        )
        .group_by(LearningClassMembership.class_id)
    )
    for class_id, total in learners.all():
        counts[int(class_id)] = counts.get(int(class_id), 0) + int(total or 0)
    return counts


async def assignment_metric_rows(db: AsyncSession, class_ids: list[int]) -> list[dict]:
    """Status, due date, and submitted count for dashboard metrics."""
    if not class_ids:
        return []
    ids = tuple(int(class_id) for class_id in class_ids)
    assignments = await db.execute(
        select(
            LearningAssignment.id,
            LearningAssignment.class_id,
            LearningAssignment.title,
            LearningAssignment.status,
            LearningAssignment.due_at,
        )
        .where(LearningAssignment.class_id.in_(ids))
        .order_by(LearningAssignment.id.desc())
    )
    submitted = await db.execute(
        select(LearningSubmission.assignment_id, func.count())
        .join(LearningAssignment, LearningAssignment.id == LearningSubmission.assignment_id)
        .where(
            LearningAssignment.class_id.in_(ids),
            LearningSubmission.status == SUBMISSION_STATUS_SUBMITTED,
        )
        .group_by(LearningSubmission.assignment_id)
    )
    submitted_by_id = {int(assignment_id): int(total or 0) for assignment_id, total in submitted.all()}
    rosters = await roster_counts_by_class(db, list(ids))
    rows: list[dict] = []
    for assignment_id, class_id, title, assignment_status, due_at in assignments.all():
        rows.append(
            {
                "id": int(assignment_id),
                "class_id": int(class_id),
                "title": title,
                "status": assignment_status,
                "due_at": due_at.isoformat() if due_at else None,
                "submitted_count": submitted_by_id.get(int(assignment_id), 0),
                "student_count": rosters.get(int(class_id), 0),
            }
        )
    return rows
