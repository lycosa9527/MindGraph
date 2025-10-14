"""
Authentication Models for MindGraph
Author: lycosa9527
Made by: MindSpring Team

Database models for User and Organization entities.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
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

