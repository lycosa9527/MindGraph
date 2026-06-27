"""Per-organization OAuth login configuration (WeChat toggle, DingTalk credentials)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.domain.auth import Base


class OrganizationOauthConfig(Base):
    """OAuth QR login settings scoped to one school organization."""

    __tablename__ = "organization_oauth_configs"
    __table_args__ = (UniqueConstraint("organization_id", name="uq_organization_oauth_configs_org"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    wechat_login_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    dingtalk_login_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    dingtalk_login_app_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    dingtalk_login_app_secret: Mapped[str | None] = mapped_column(Text, nullable=True)
    dingtalk_corp_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    organization = relationship("Organization", lazy="select")
