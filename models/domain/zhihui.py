"""ZhiHui (智绘) conversation and generation history models."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.domain.auth import Base


def generate_zhihui_id() -> str:
    """Generate a UUID string for ZhiHui entity IDs."""
    return str(uuid.uuid4())


class ZhihuiConversation(Base):
    """One ZhiHui history conversation (image turn or diagram lesson deck)."""

    __tablename__ = "zhihui_conversations"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_zhihui_id,
        index=True,
    )
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )
    organization_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    mode: Mapped[str] = mapped_column(String(16), nullable=False, default="image", index=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    diagram_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    diagram_title: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    style_seed: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    planner_model: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    image_model: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    lesson_plan_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="complete", index=True)
    progress: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    celery_task_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    language: Mapped[str] = mapped_column(String(16), nullable=False, default="zh")
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

    generations: Mapped[list["ZhihuiGeneration"]] = relationship(
        "ZhihuiGeneration",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="ZhihuiGeneration.slide_index",
    )

    __table_args__ = (Index("ix_zhihui_conversations_updated_at_desc", "updated_at"),)


class ZhihuiGeneration(Base):
    """Persisted text-to-image generation (COS logical key + metadata)."""

    __tablename__ = "zhihui_generations"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_zhihui_id,
        index=True,
    )
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )
    organization_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    enhanced_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    language: Mapped[str] = mapped_column(String(16), nullable=False, default="zh")
    conversation_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("zhihui_conversations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    dify_conversation_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    dify_user_id: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    cos_logical_key: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str] = mapped_column(String(64), nullable=False, default="image/jpeg")
    size: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    api_key_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    slide_index: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    slide_title: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    teacher_script: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    focus_node_ids: Mapped[Optional[list[Any]]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
    )

    conversation: Mapped[Optional[ZhihuiConversation]] = relationship(
        "ZhihuiConversation",
        back_populates="generations",
    )

    __table_args__ = (
        Index("ix_zhihui_generations_created_at_desc", "created_at"),
        Index(
            "uq_zhihui_generations_conversation_slide",
            "conversation_id",
            "slide_index",
            unique=True,
            postgresql_where=text("conversation_id IS NOT NULL AND slide_index IS NOT NULL"),
        ),
    )
