"""Per-organization MindBot (DingTalk HTTP ↔ Dify) configuration."""

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.domain.auth import Base


class OrganizationMindbotConfig(Base):
    """Stores DingTalk app credentials and Dify endpoint per school (organization)."""

    __tablename__ = "organization_mindbot_configs"
    __table_args__ = (
        UniqueConstraint("dingtalk_robot_code", name="uq_mindbot_config_robot_code"),
        UniqueConstraint("public_callback_token", name="uq_mindbot_config_public_callback_token"),
        Index("ix_mindbot_config_organization_id", "organization_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    bot_label: Mapped[str | None] = mapped_column(String(64), nullable=True)
    dingtalk_robot_code: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    public_callback_token: Mapped[str] = mapped_column(String(64), nullable=False)
    dingtalk_app_secret: Mapped[str] = mapped_column(Text, nullable=False)
    dingtalk_client_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    dingtalk_event_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    dingtalk_event_aes_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    dingtalk_event_owner_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    dify_api_base_url: Mapped[str] = mapped_column(String(512), nullable=False)
    dify_api_key: Mapped[str] = mapped_column(Text, nullable=False)
    dify_inputs_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    dify_timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=300)
    show_chain_of_thought_oto: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    show_chain_of_thought_internal_group: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    show_chain_of_thought_cross_org_group: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    chain_of_thought_max_chars: Mapped[int] = mapped_column(Integer, nullable=False, default=4000)
    dingtalk_ai_card_template_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    dingtalk_ai_card_param_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    dingtalk_ai_card_streaming_max_chars: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=6500,
    )
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

    organization = relationship("Organization", lazy="select")
