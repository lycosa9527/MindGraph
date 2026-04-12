"""Per-organization MindBot (DingTalk HTTP ↔ Dify) configuration."""

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.domain.auth import Base


class OrganizationMindbotConfig(Base):
    """Stores DingTalk app credentials and Dify endpoint per school (organization)."""

    __tablename__ = "organization_mindbot_configs"
    __table_args__ = (
        UniqueConstraint("organization_id", name="uq_mindbot_config_organization_id"),
        UniqueConstraint("dingtalk_robot_code", name="uq_mindbot_config_robot_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    dingtalk_robot_code: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    dingtalk_app_secret: Mapped[str] = mapped_column(Text, nullable=False)
    dingtalk_client_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    dingtalk_event_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    dingtalk_event_aes_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    dingtalk_event_owner_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    dify_api_base_url: Mapped[str] = mapped_column(String(512), nullable=False)
    dify_api_key: Mapped[str] = mapped_column(Text, nullable=False)
    dify_inputs_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    dify_timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    organization = relationship("Organization", lazy="selectin")
