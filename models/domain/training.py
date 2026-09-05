"""
Training course catalog — authored lessons for 校本培训.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects import postgresql as pg
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.domain.auth import Base

if TYPE_CHECKING:
    from models.domain.auth import User


def generate_training_uuid() -> str:
    """Generate a UUID string for training course rows."""
    return str(uuid.uuid4())


class TrainingCourse(Base):
    """Persisted training course (WISE-style project, media on COS)."""

    __tablename__ = "training_courses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_training_uuid, index=True)
    owner_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    title: Mapped[dict] = mapped_column(pg.JSONB, nullable=False, default=dict)
    description: Mapped[dict] = mapped_column(pg.JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True)
    cover_asset_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    owner: Mapped[Optional["User"]] = relationship("User", foreign_keys=[owner_id], lazy="selectin")
    steps: Mapped[list["TrainingCourseStep"]] = relationship(
        "TrainingCourseStep",
        back_populates="course",
        cascade="all, delete-orphan",
        order_by="TrainingCourseStep.position",
        lazy="selectin",
    )
    assets: Mapped[list["TrainingCourseAsset"]] = relationship(
        "TrainingCourseAsset",
        back_populates="course",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (Index("ix_training_courses_status_updated", "status", "updated_at"),)


class TrainingCourseStep(Base):
    """Ordered step: canvas, slide, or video."""

    __tablename__ = "training_course_steps"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_training_uuid, index=True)
    course_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("training_courses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    step_type: Mapped[str] = mapped_column(String(20), nullable=False)
    payload: Mapped[dict] = mapped_column(pg.JSONB, nullable=False, default=dict)

    course: Mapped["TrainingCourse"] = relationship("TrainingCourse", back_populates="steps")

    __table_args__ = (Index("ix_training_course_steps_course_pos", "course_id", "position"),)


class TrainingCourseAsset(Base):
    """COS object bound to one course folder."""

    __tablename__ = "training_course_assets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_training_uuid, index=True)
    course_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("training_courses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    logical_key: Mapped[str] = mapped_column(String(512), nullable=False)
    mime: Mapped[str] = mapped_column(String(128), nullable=False)
    bytes_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    course: Mapped["TrainingCourse"] = relationship("TrainingCourse", back_populates="assets")

    __table_args__ = (Index("ix_training_course_assets_course_role", "course_id", "role"),)
