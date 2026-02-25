"""Authentication Models for MindGraph.

Author: lycosa9527
Made by: MindSpring Team

Database models for User and Organization entities.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Mapped, mapped_column, relationship


Base = declarative_base()


class Organization(Base):
    """
    Organization/School model

    Represents schools or educational institutions.
    Each organization has a unique code and invitation code for registration.
    """
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, index=True, nullable=False)  # e.g., "DEMO-001"
    name = Column(String(200), nullable=False)  # e.g., "Demo School for Testing"
    invitation_code = Column(String(50), nullable=True)  # For controlled registration
    created_at = Column(DateTime, default=datetime.utcnow)

    # Service subscription management
    expires_at = Column(DateTime, nullable=True)  # Service expiration date
    is_active = Column(Boolean, default=True)  # Active/locked status

    # Relationship
    users = relationship("User", back_populates="organization")


class User(Base):
    """
    User model for K12 teachers

    Stores user credentials and security information.
    Password is hashed using bcrypt.

    Roles:
    - 'user': Regular user (default)
    - 'manager': Organization manager, can access org-scoped admin dashboard
    - 'admin': Full admin access to all data
    """
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    phone: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    organization_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("organizations.id"), nullable=True
    )
    avatar: Mapped[str | None] = mapped_column(String(50), nullable=True, default="🐈‍⬛")
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="user")

    # Security fields
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_login: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    organization = relationship("Organization", back_populates="users")
    diagrams = relationship("Diagram", back_populates="user", lazy="dynamic")


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

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)  # e.g., "Dify Integration"
    description = Column(String)

    # Quota & Usage Tracking
    quota_limit = Column(Integer, nullable=True)  # null = unlimited
    usage_count = Column(Integer, default=0)

    # Status
    is_active = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)

    # Optional: Link to organization
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)

    def __repr__(self):
        return f"<APIKey {self.name}: {self.key[:12]}...>"


class UpdateNotification(Base):
    """
    Update Notification Configuration

    Stores the current announcement settings.
    Only one active record should exist (id=1).
    """
    __tablename__ = "update_notifications"

    id = Column(Integer, primary_key=True, index=True)
    enabled = Column(Boolean, default=False)
    version = Column(String(50), default="")
    title = Column(String(200), default="")
    message = Column(String(10000), default="")  # Rich text content

    # Scheduling - optional start/end dates
    start_date = Column(DateTime, nullable=True)  # Show after this date
    end_date = Column(DateTime, nullable=True)    # Hide after this date

    # Targeting - optional organization filter
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)

    updated_at = Column(DateTime, default=datetime.utcnow)


class UpdateNotificationDismissed(Base):
    """
    Tracks which users have dismissed which version of the notification.

    When user dismisses, their user_id + version is stored.
    When version changes, old records can be cleaned up.
    """
    __tablename__ = "update_notification_dismissed"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    version = Column(String(50), nullable=False, index=True)
    dismissed_at = Column(DateTime, default=datetime.utcnow)

    # Unique constraint: one dismiss record per user per version (prevents duplicates)
    __table_args__ = (
        UniqueConstraint('user_id', 'version', name='uq_user_version_dismissed'),
    )


# NOTE: Captcha model removed - captchas are now stored in Redis
# See: services/captcha_storage.py
# The captchas table may still exist in the database but is no longer used.

# NOTE: SMSVerification model removed - SMS codes are now stored in Redis
# See: services/redis_sms_storage.py
# The sms_verifications table may still exist in the database but is no longer used.
