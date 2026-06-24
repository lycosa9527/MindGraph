"""Durable preview id → library diagram mapping for MindMate / MindBot generations."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects import postgresql as pg
from sqlalchemy.orm import Mapped, mapped_column

from models.domain.auth import Base


class GenerationPreviewLink(Base):
    """
    Long-lived lookup from generate_dingtalk temp PNG id (8 hex) to library state.

    Redis ``mg:gen_lib_skip:*`` remains a hot cache (24h); this table survives reopening
    old Dify conversations days later.
    """

    __tablename__ = "generation_preview_links"

    preview_id: Mapped[str] = mapped_column(String(8), primary_key=True)
    diagram_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("diagrams.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    organization_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
    )
    skip_reason: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    language: Mapped[str] = mapped_column(String(16), nullable=False, default="zh")
    diagram_type: Mapped[str] = mapped_column(String(64), nullable=False, default="mind_map")
    title: Mapped[str] = mapped_column(String(200), nullable=False, default="Diagram")
    spec: Mapped[Optional[dict]] = mapped_column(pg.JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    def __repr__(self) -> str:
        return f"<GenerationPreviewLink preview={self.preview_id!r} diagram={self.diagram_id!r} user={self.user_id}>"
