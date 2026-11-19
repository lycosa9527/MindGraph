"""Learning Space (student classroom pilot) ORM models.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.domain.auth import Base

if TYPE_CHECKING:
    from models.domain.auth import Organization, User

CLASS_STATUS_ACTIVE = "active"
CLASS_STATUS_ARCHIVED = "archived"
CLASS_STATUSES = frozenset({CLASS_STATUS_ACTIVE, CLASS_STATUS_ARCHIVED})

ASSIGNMENT_STATUS_ACTIVE = "active"
ASSIGNMENT_STATUS_CLOSED = "closed"
ASSIGNMENT_STATUS_DRAFT = "draft"
ASSIGNMENT_STATUSES = frozenset({ASSIGNMENT_STATUS_ACTIVE, ASSIGNMENT_STATUS_CLOSED, ASSIGNMENT_STATUS_DRAFT})

MEMBERSHIP_ROLE_LEARNER = "learner"
MEMBERSHIP_ROLE_ASSISTANT = "assistant"
MEMBERSHIP_ROLES = frozenset({MEMBERSHIP_ROLE_LEARNER, MEMBERSHIP_ROLE_ASSISTANT})

SUBMISSION_STATUS_DRAFT = "draft"
SUBMISSION_STATUS_SUBMITTED = "submitted"
SUBMISSION_STATUS_RETURNED = "returned"
SUBMISSION_STATUSES = frozenset(
    {
        SUBMISSION_STATUS_DRAFT,
        SUBMISSION_STATUS_SUBMITTED,
        SUBMISSION_STATUS_RETURNED,
    }
)

# Granular canvas tools controlled by the teacher publish UI.
GRANULAR_AI_CAPABILITIES: frozenset[str] = frozenset(
    {
        "topic_generate",
        "file_generate",
        "web_generate",
        "voice_summary",
        "ai_brainstorm",
        "conversational_edit",
        "node_subgraph",
        "node_explain",
        "mind_classroom",
    }
)

# Legacy capability names → granular keys (older assignments / older gate call sites).
LEGACY_AI_CAPABILITY_ALIASES: dict[str, str] = {
    "generate_diagram": "topic_generate",
    "inline_recommend": "ai_brainstorm",
    "doc_summary": "file_generate",
}

DEFAULT_AI_PERMISSIONS: dict[str, bool] = {
    "ai_assist": False,
    "topic_generate": False,
    "file_generate": False,
    "web_generate": False,
    "voice_summary": False,
    "ai_brainstorm": False,
    "conversational_edit": False,
    "node_subgraph": False,
    "node_explain": False,
    "mind_classroom": False,
    # Legacy keys kept for older assignments / older API consumers.
    "generate_diagram": False,
    "inline_recommend": False,
    "translate": False,
    "doc_summary": False,
}


def _utc_now() -> datetime:
    """Naive UTC for TIMESTAMP WITHOUT TIME ZONE columns."""
    return datetime.now(UTC).replace(tzinfo=None)


class LearningPilotTeacher(Base):
    """Superadmin grant allowing a teacher to use Learning Space classes."""

    __tablename__ = "learning_pilot_teachers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    teacher_user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    organization_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)

    teacher: Mapped["User"] = relationship("User", foreign_keys=[teacher_user_id], lazy="selectin")
    organization: Mapped["Organization"] = relationship("Organization", lazy="selectin")


class LearningClass(Base):
    """Classroom with a public class_code for student login."""

    __tablename__ = "learning_classes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    class_code: Mapped[str] = mapped_column(String(16), nullable=False, unique=True, index=True)
    teacher_user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=CLASS_STATUS_ACTIVE)
    max_students: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=_utc_now,
        onupdate=_utc_now,
    )

    teacher: Mapped["User"] = relationship("User", foreign_keys=[teacher_user_id], lazy="selectin")
    organization: Mapped["Organization"] = relationship("Organization", lazy="selectin")
    assignments: Mapped[list["LearningAssignment"]] = relationship(
        "LearningAssignment",
        back_populates="learning_class",
        cascade="all, delete-orphan",
        lazy="select",
    )


class LearningClassMembership(Base):
    """Existing-account enrollment: learner (homework) or assistant (publish and grade)."""

    __tablename__ = "learning_class_memberships"
    __table_args__ = (UniqueConstraint("class_id", "user_id", name="uq_learning_class_memberships_class_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    class_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("learning_classes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False, default=MEMBERSHIP_ROLE_LEARNER)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)

    learning_class: Mapped["LearningClass"] = relationship("LearningClass", lazy="selectin")
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id], lazy="selectin")


class LearningAssignment(Base):
    """Homework assigned to a learning class from a template diagram."""

    __tablename__ = "learning_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    class_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("learning_classes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    instructions: Mapped[str] = mapped_column(Text, nullable=False, default="")
    template_diagram_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ai_permissions: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    instruction_images: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    organization_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=ASSIGNMENT_STATUS_ACTIVE)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=_utc_now,
        onupdate=_utc_now,
    )

    learning_class: Mapped["LearningClass"] = relationship(
        "LearningClass",
        back_populates="assignments",
        lazy="selectin",
    )
    submissions: Mapped[list["LearningSubmission"]] = relationship(
        "LearningSubmission",
        back_populates="assignment",
        cascade="all, delete-orphan",
        lazy="select",
    )


class LearningSubmission(Base):
    """Per-student homework diagram and submission state."""

    __tablename__ = "learning_submissions"
    __table_args__ = (
        UniqueConstraint("assignment_id", "student_user_id", name="uq_learning_submission_assignment_student"),
        Index("ix_learning_submissions_student", "student_user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    assignment_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("learning_assignments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    student_user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    diagram_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=SUBMISSION_STATUS_DRAFT)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    due_at_override: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    snapshot_spec: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    review_scores: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    review_comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    review_liked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    review_pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reviewed_by: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=_utc_now,
        onupdate=_utc_now,
    )

    assignment: Mapped["LearningAssignment"] = relationship(
        "LearningAssignment",
        back_populates="submissions",
        lazy="selectin",
    )
    student: Mapped["User"] = relationship("User", foreign_keys=[student_user_id], lazy="selectin")


class LearningSheetToken(Base):
    """Printed learning-sheet QR. The UUID names the course diagram, not the student."""

    __tablename__ = "learning_sheet_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    diagram_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    course_spec: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)


class LearningSheetCapture(Base):
    """One glasses photo of a printed sheet, plus the server OCR result."""

    __tablename__ = "learning_sheet_captures"
    __table_args__ = (Index("ix_learning_sheet_captures_owner_created", "owner_user_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sheet_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("learning_sheet_tokens.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    owner_user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    image_ref: Mapped[str] = mapped_column(String(240), nullable=False)
    student_name: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    class_name: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    ocr_spec: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    ocr_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    copy_seq: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)


class LearningSheetCopy(Base):
    """One printed page of a class set. The sequence is the number in that page's QR."""

    __tablename__ = "learning_sheet_copies"
    __table_args__ = (UniqueConstraint("sheet_id", "seq", name="uq_learning_sheet_copies_sheet_seq"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sheet_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("learning_sheet_tokens.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    student_user_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    student_name: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    class_name: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    owner_user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)


class GlassesWearerBind(Base):
    """QR the signed-in user shows so the glasses photo is stored on that account."""

    __tablename__ = "glasses_wearer_binds"
    __table_args__ = (UniqueConstraint("owner_user_id", name="uq_glasses_wearer_binds_owner"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    image_ref: Mapped[str | None] = mapped_column(String(240), nullable=True)
    bound_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
