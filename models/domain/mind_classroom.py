"""Mind Classroom lecture job and slide models."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.domain.auth import Base


def generate_classroom_id() -> str:
    """Generate a UUID string for classroom entity IDs."""
    return str(uuid.uuid4())


class MindClassroomJob(Base):
    """One lecture generation job (canvas tour or slide deck)."""

    __tablename__ = "mind_classroom_jobs"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_classroom_id,
        index=True,
    )
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    organization_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    diagram_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    spec_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    settings: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    spec_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued", index=True)
    current_stage: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    progress: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    result_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    lesson_plan_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    celery_task_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    attempts: Mapped[Optional[list[Any]]] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    slides: Mapped[list["MindClassroomSlide"]] = relationship(
        "MindClassroomSlide",
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="MindClassroomSlide.slide_index",
    )

    __table_args__ = (
        Index("ix_mind_classroom_jobs_user_status", "user_id", "status"),
        Index("ix_mind_classroom_jobs_reuse", "user_id", "spec_hash"),
    )


class MindClassroomSlide(Base):
    """One generated slide image for a slide_deck job."""

    __tablename__ = "mind_classroom_slides"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_classroom_id,
        index=True,
    )
    job_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("mind_classroom_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    slide_index: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    teacher_script: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    focus_node_ids: Mapped[Optional[list[Any]]] = mapped_column(JSONB, nullable=True)
    cos_logical_key: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str] = mapped_column(String(64), nullable=False, default="image/png")
    size: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    job: Mapped[MindClassroomJob] = relationship("MindClassroomJob", back_populates="slides")

    __table_args__ = (Index("ix_mind_classroom_slides_job_index", "job_id", "slide_index", unique=True),)
