"""
Token Usage Tracking Models
Stores LLM token usage and costs for analytics.
Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.domain.auth import Base

if TYPE_CHECKING:
    from models.domain.auth import APIKey, Organization, User


class TokenUsage(Base):
    """Track token usage and costs for all LLM calls"""

    __tablename__ = "token_usage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    organization_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("organizations.id"), nullable=True)
    api_key_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("api_keys.id"), nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(100), index=True)
    conversation_id: Mapped[str | None] = mapped_column(String(100), index=True)

    model_provider: Mapped[str | None] = mapped_column(String(50), index=True)
    model_name: Mapped[str | None] = mapped_column(String(100), index=True)
    model_alias: Mapped[str | None] = mapped_column(String(50), index=True)

    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)

    input_cost: Mapped[float] = mapped_column(Float, default=0.0)
    output_cost: Mapped[float] = mapped_column(Float, default=0.0)
    total_cost: Mapped[float] = mapped_column(Float, default=0.0)

    request_type: Mapped[str | None] = mapped_column(String(50), index=True)
    diagram_type: Mapped[str | None] = mapped_column(String(50))
    endpoint_path: Mapped[str | None] = mapped_column(String(200))
    success: Mapped[bool] = mapped_column(Boolean, default=True)

    response_time: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    user: Mapped["User | None"] = relationship("User", foreign_keys=[user_id], lazy="select")
    organization: Mapped["Organization | None"] = relationship(
        "Organization",
        foreign_keys=[organization_id],
        lazy="select",
    )
    api_key: Mapped["APIKey | None"] = relationship("APIKey", foreign_keys=[api_key_id], lazy="select")

    __table_args__ = (
        Index("idx_token_usage_user_date", "user_id", "created_at"),
        Index("idx_token_usage_org_date", "organization_id", "created_at"),
        Index("idx_token_usage_api_key_date", "api_key_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<TokenUsage(user_id={self.user_id}, model={self.model_alias}, tokens={self.total_tokens})>"
