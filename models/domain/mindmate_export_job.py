"""
MindMate export background job persistence.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from models.domain.auth import Base


class MindmateExportJob(Base):
    """Long-running MindMate conversation export job."""

    __tablename__ = "mindmate_export_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    created_by_user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        Enum(
            "pending",
            "running",
            "paused",
            "completed",
            "completed_with_gaps",
            "failed",
            "failed_verification",
            "cancelled",
            name="mindmate_export_job_status",
        ),
        default="pending",
        nullable=False,
        index=True,
    )
    current_stage: Mapped[str | None] = mapped_column(String(64), nullable=True)
    progress_percent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    progress_detail: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    filters: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    checkpoint: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    verification_expected: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    verification_report: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    artifact_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    artifact_format: Mapped[str | None] = mapped_column(String(16), nullable=True)
    artifact_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    artifact_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancel_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<MindmateExportJob id={self.id} status={self.status}>"
