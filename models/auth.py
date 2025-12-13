"""
Authentication Models for MindGraph
Author: lycosa9527
Made by: MindSpring Team

Database models for User and Organization entities.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

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
    """
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String(20), unique=True, index=True, nullable=False)  # 11-digit Chinese mobile
    password_hash = Column(String(255), nullable=False)  # bcrypt hashed password
    name = Column(String(100), nullable=True)  # Teacher's name (optional)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    
    # Security fields
    failed_login_attempts = Column(Integer, default=0)  # Track failed logins
    locked_until = Column(DateTime, nullable=True)  # Account lockout timestamp
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    
    # Relationship
    organization = relationship("Organization", back_populates="users")


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


class Captcha(Base):
    """
    Temporary captcha storage for verification.
    
    Uses SQLite with WAL mode for multi-worker compatibility.
    Captchas are one-time use and expire after 5 minutes.
    """
    __tablename__ = "captchas"
    
    id = Column(String(64), primary_key=True)  # UUID
    code = Column(String(10), nullable=False)  # Captcha code (uppercase)
    expires_at = Column(DateTime, nullable=False)  # Expiration timestamp
    created_at = Column(DateTime, default=datetime.utcnow)


class SMSVerification(Base):
    """
    SMS Verification Code Storage
    
    Stores SMS verification codes for:
    - Account registration
    - SMS login
    - Password reset
    
    Features:
    - Time-limited codes (default 5 minutes)
    - Rate limiting per phone number
    - Purpose-based verification (register/login/reset_password)
    - One-time use (marked as used after verification)
    """
    __tablename__ = "sms_verifications"
    
    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String(20), nullable=False, index=True)  # Phone number
    code = Column(String(10), nullable=False)  # 6-digit verification code
    purpose = Column(String(20), nullable=False)  # register, login, reset_password
    
    # Status tracking
    is_used = Column(Boolean, default=False)  # One-time use flag
    attempts = Column(Integer, default=0)  # Failed verification attempts
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)  # Expiration timestamp
    used_at = Column(DateTime, nullable=True)  # When code was successfully used
    
    # Composite index for efficient lookups
    __table_args__ = (
        UniqueConstraint('phone', 'code', 'purpose', name='uq_phone_code_purpose'),
    )

