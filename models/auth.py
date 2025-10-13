"""
Authentication Models for MindGraph
Author: lycosa9527
Made by: MindSpring Team

Database models for User and Organization entities.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
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

