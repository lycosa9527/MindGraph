"""Authentication Models for MindGraph.

Author: lycosa9527
Made by: MindSpring Team

Database models for User and Organization entities.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from utils.user_avatar_defaults import DEFAULT_USER_AVATAR_EMOJI

if TYPE_CHECKING:
    from models.domain.diagrams import Diagram


class Base(DeclarativeBase):
    """Shared declarative base for all MindGraph ORM models."""


MINDMATE_AGENT_NAME_MAX_LENGTH = 10


class Organization(Base):
    """
    Organization/School model

    Represents schools or educational institutions.
    Each organization has a unique code and invitation code for registration.
    """

    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    invitation_code: Mapped[str | None] = mapped_column(String(50), unique=True, nullable=True)
    invited_by_user_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    school_tier: Mapped[str] = mapped_column(String(32), nullable=False, default="trial")
    extra_member_seats: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    dify_api_base_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    dify_api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    dify_timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=300)
    show_chain_of_thought_oto: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    show_chain_of_thought_internal_group: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    show_chain_of_thought_cross_org_group: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    chain_of_thought_max_chars: Mapped[int] = mapped_column(Integer, nullable=False, default=4000)
    dingtalk_ai_card_streaming_max_chars: Mapped[int] = mapped_column(Integer, nullable=False, default=6500)

    mindmate_agent_name: Mapped[str | None] = mapped_column(String(MINDMATE_AGENT_NAME_MAX_LENGTH), nullable=True)
    mindmate_agent_avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    users: Mapped[list["User"]] = relationship(
        "User",
        back_populates="organization",
        lazy="select",
        foreign_keys="User.organization_id",
    )


class User(Base):
    """
    User model for K12 teachers

    Stores user credentials and security information.
    Password is hashed using bcrypt.

    Roles (canonical slugs):
    - 'superadmin': Full platform admin (超级管理员)
    - 'platform_bd': Teaching researcher (教研员) — read-only global dashboard
    - 'expert': Platform expert — B2B school invites (own orgs)
    - 'school_admin': Organization manager (学校管理员) — own-school dashboard + user mgmt
    - 'teacher': B2B school member (教师用户)
    - 'personal_trial': C-end trial account (个人体验账号)
    - 'personal_paid': C-end paid account (个人付费账号)
    """

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "phone IS NOT NULL OR email IS NOT NULL",
            name="ck_users_phone_or_email",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    organization_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("organizations.id", ondelete="SET NULL"), index=True, nullable=True
    )
    avatar: Mapped[str | None] = mapped_column(String(50), nullable=True, default=DEFAULT_USER_AVATAR_EMOJI)
    role: Mapped[str] = mapped_column(String(30), nullable=False, default="teacher")

    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    last_login: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    workshop_last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    ui_language: Mapped[str | None] = mapped_column(String(32), nullable=True)
    prompt_language: Mapped[str | None] = mapped_column(String(32), nullable=True)
    match_prompt_to_ui: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    ui_version: Mapped[str | None] = mapped_column(String(32), nullable=True, default="international")
    allows_simplified_chinese: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    email_login_whitelisted_from_cn: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    login_password_set: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    organization: Mapped["Organization | None"] = relationship(
        "Organization",
        back_populates="users",
        lazy="select",
        foreign_keys="User.organization_id",
    )
    diagrams: Mapped[list["Diagram"]] = relationship(
        "Diagram",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="select",
    )


class APIKey(Base):
    """
    API Key model for public API access (Dify, partners, etc.)

    Features:
    - Unique API key with mg_ prefix
    - Usage tracking and quota limits
    - Expiration dates
    - Active/inactive status
    - Optional organization linkage
    """

    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    key: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)

    quota_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    usage_count: Mapped[int] = mapped_column(Integer, default=0)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    organization_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("organizations.id", ondelete="SET NULL"), index=True, nullable=True
    )

    def __repr__(self) -> str:
        return f"<APIKey {self.name}: {self.key[:12]}...>"


class UpdateNotification(Base):
    """
    Update Notification Configuration

    Stores the current announcement settings.
    Only one active record should exist (id=1).
    """

    __tablename__ = "update_notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    version: Mapped[str] = mapped_column(String(50), default="")
    title: Mapped[str] = mapped_column(String(200), default="")
    message: Mapped[str] = mapped_column(String(10000), default="")

    start_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    end_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    organization_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("organizations.id"), nullable=True)

    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))


class UpdateNotificationDismissed(Base):
    """
    Tracks which users have dismissed which version of the notification.

    When user dismisses, their user_id + version is stored.
    When version changes, old records can be cleaned up.
    """

    __tablename__ = "update_notification_dismissed"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    dismissed_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    __table_args__ = (UniqueConstraint("user_id", "version", name="uq_user_version_dismissed"),)


# NOTE: Captcha model removed - captchas are now stored in Redis
# See: services/captcha_storage.py
# The captchas table may still exist in the database but is no longer used.

# NOTE: SMSVerification model removed - SMS codes are now stored in Redis
# See: services/redis_sms_storage.py
# The sms_verifications table may still exist in the database but is no longer used.
