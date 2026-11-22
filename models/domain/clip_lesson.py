"""Clip-teaching lessons: one video, one deck, chapters, and org comments."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.domain.auth import Base

PREVIEW_NONE = "none"
PREVIEW_PENDING = "pending"
PREVIEW_READY = "ready"
PREVIEW_FAILED = "failed"
PREVIEW_STATUSES = frozenset({PREVIEW_NONE, PREVIEW_PENDING, PREVIEW_READY, PREVIEW_FAILED})


def generate_clip_lesson_id() -> str:
    """Generate a UUID string for a lesson row."""
    return str(uuid.uuid4())


class ClipLesson(Base):
    """One teaching slice owned by a teacher and visible to their organization."""

    __tablename__ = "clip_lessons"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_clip_lesson_id)
    organization_id: Mapped[int] = mapped_column(Integer, ForeignKey("organizations.id"), nullable=False)
    owner_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    vod_media_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("vod_media.id", ondelete="SET NULL"),
        nullable=True,
    )
    local_video_key: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    trim_start_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    trim_end_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    deck_key: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    preview_pdf_key: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    preview_status: Mapped[str] = mapped_column(String(20), nullable=False, default=PREVIEW_NONE)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    chapters: Mapped[list["ClipLessonChapter"]] = relationship(
        back_populates="lesson",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ClipLessonChapter.start_ms",
    )
    comments: Mapped[list["ClipLessonComment"]] = relationship(
        back_populates="lesson",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        Index("ix_clip_lessons_organization_id", "organization_id"),
        Index("ix_clip_lessons_owner_id", "owner_id"),
        Index("ix_clip_lessons_org_updated", "organization_id", "updated_at"),
    )


class ClipLessonChapter(Base):
    """A named point on the lesson timeline. The next chapter is the end."""

    __tablename__ = "clip_lesson_chapters"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_clip_lesson_id)
    lesson_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("clip_lessons.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(80), nullable=False)
    start_ms: Mapped[int] = mapped_column(Integer, nullable=False)

    lesson: Mapped[ClipLesson] = relationship(back_populates="chapters")

    __table_args__ = (
        UniqueConstraint("lesson_id", "start_ms", name="uq_clip_lesson_chapters_start"),
        Index("ix_clip_lesson_chapters_lesson_id", "lesson_id"),
    )


class ClipLessonComment(Base):
    """Organization comment. ``parent_id`` is set only for a reply to a root comment."""

    __tablename__ = "clip_lesson_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lesson_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("clip_lessons.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    parent_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("clip_lesson_comments.id", ondelete="CASCADE"),
        nullable=True,
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    lesson: Mapped[ClipLesson] = relationship(back_populates="comments")

    __table_args__ = (
        Index("ix_clip_lesson_comments_lesson_id", "lesson_id"),
        Index("ix_clip_lesson_comments_user_id", "user_id"),
        Index("ix_clip_lesson_comments_parent_id", "parent_id"),
    )
