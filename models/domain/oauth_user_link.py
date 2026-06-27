"""Maps WeChat or DingTalk OAuth identity to a MindGraph user within an organization."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.domain.auth import Base

OAUTH_PROVIDER_WECHAT = "wechat"
OAUTH_PROVIDER_DINGTALK = "dingtalk"
OAUTH_PROVIDERS = frozenset({OAUTH_PROVIDER_WECHAT, OAUTH_PROVIDER_DINGTALK})


class OauthUserLink(Base):
    """External OAuth identity linked to one user in one organization."""

    __tablename__ = "oauth_user_links"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "provider",
            "external_id",
            name="uq_oauth_user_links_org_provider_external",
        ),
        UniqueConstraint(
            "organization_id",
            "user_id",
            "provider",
            name="uq_oauth_user_links_org_user_provider",
        ),
        Index("ix_oauth_user_links_user_org", "user_id", "organization_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    external_id: Mapped[str] = mapped_column(String(128), nullable=False)
    openid: Mapped[str | None] = mapped_column(String(128), nullable=True)
    nickname: Mapped[str | None] = mapped_column(String(128), nullable=True)
    linked_via: Mapped[str] = mapped_column(String(32), nullable=False, default="self")
    linked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    user = relationship("User", foreign_keys=[user_id], lazy="select")
