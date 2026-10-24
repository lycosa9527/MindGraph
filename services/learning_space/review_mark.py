"""Whether a homework row still holds a saved review.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import ColumnElement, func, or_

from models.domain.learning_space import SUBMISSION_STATUS_SUBMITTED, LearningSubmission


def submission_has_review() -> ColumnElement[bool]:
    """Rows that still hold any column written by save or cleared on resubmit."""
    return or_(
        LearningSubmission.reviewed_by.is_not(None),
        LearningSubmission.reviewed_at.is_not(None),
        LearningSubmission.review_comment.is_not(None),
        LearningSubmission.review_scores.is_not(None),
        LearningSubmission.review_liked.is_(True),
        LearningSubmission.review_pinned.is_(True),
    )


def current_submission() -> ColumnElement[bool]:
    """Homework that is still handed in. Returned rows keep review columns and stay out."""
    return LearningSubmission.status == SUBMISSION_STATUS_SUBMITTED


def submission_tally_columns() -> tuple[ColumnElement[Any], ColumnElement[Any]]:
    """Submitted rows, and the subset of those rows that still hold a review."""
    return (
        func.count(LearningSubmission.id),
        func.count(LearningSubmission.id).filter(submission_has_review()),
    )
