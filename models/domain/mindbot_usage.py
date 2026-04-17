"""Per-event MindBot (DingTalk) usage for university analytics and cross-product joins."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.domain.auth import Base


class MindbotUsageEvent(Base):
    """
    One row per processed DingTalk callback attempt (success or failure).

    Identifies humans by DingTalk ``senderStaffId`` and optional ``senderNick`` from
    the callback body. ``linked_user_id`` is optional for future SSO / account linking
    to MindGraph ``users`` (MindMate, diagrams).

    Educational research fields: ``dingtalk_chat_scope`` (group vs one-to-one),
    ``inbound_msg_type`` (text vs media modality), ``conversation_user_turn`` (nth
    user message in the DingTalk thread, from Redis).
    """

    __tablename__ = "mindbot_usage_events"
    __table_args__ = (
        Index("ix_mindbot_usage_org_created", "organization_id", "created_at"),
        Index("ix_mindbot_usage_staff_org", "dingtalk_staff_id", "organization_id"),
        Index("ix_mindbot_usage_org_id_desc", "organization_id", "id"),
        Index(
            "ix_mindbot_usage_org_thread_id",
            "organization_id",
            "dingtalk_conversation_id",
            "id",
        ),
        Index("ix_mindbot_usage_dify_conv", "dify_conversation_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    mindbot_config_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("organization_mindbot_configs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    dingtalk_staff_id: Mapped[str] = mapped_column(String(128), nullable=False)
    sender_nick: Mapped[str | None] = mapped_column(String(256), nullable=True)
    dingtalk_sender_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    dify_user_key: Mapped[str] = mapped_column(String(256), nullable=False)
    msg_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    dingtalk_conversation_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    dify_conversation_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    error_code: Mapped[str] = mapped_column(String(64), nullable=False)
    streaming: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    prompt_chars: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reply_chars: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)

    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)

    dingtalk_chat_scope: Mapped[str | None] = mapped_column(String(16), nullable=True)
    inbound_msg_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    conversation_user_turn: Mapped[int | None] = mapped_column(Integer, nullable=True)

    linked_user_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )

    organization = relationship("Organization", lazy="select")
    mindbot_config = relationship("OrganizationMindbotConfig", lazy="select")
    linked_user = relationship("User", foreign_keys=[linked_user_id], lazy="select")
