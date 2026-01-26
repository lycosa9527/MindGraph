"""
School Zone Models for MindGraph
Author: lycosa9527
Made by: MindSpring Team

Database models for organization-scoped content sharing.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Text, Index
from sqlalchemy.orm import relationship

from models.domain.auth import Base


def generate_uuid():
    """Generate a UUID string for shared diagram IDs."""
    return str(uuid.uuid4())


class SharedDiagram(Base):
    """
    Shared Diagram model for organization-scoped sharing

    Represents diagrams or MindMate courses shared within an organization.
    Only users from the same organization can view shared content.
    Uses UUID for secure, non-guessable IDs.
    """
    __tablename__ = "shared_diagrams"

    id = Column(String(36), primary_key=True, default=generate_uuid, index=True)

    # Content info
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    content_type = Column(String(50), nullable=False)  # 'mindgraph' or 'mindmate'
    category = Column(String(50), nullable=True)  # e.g., '教学设计', '学科资源'

    # The actual diagram data (JSON string)
    diagram_data = Column(Text, nullable=True)

    # Thumbnail/preview (base64 or URL)
    thumbnail = Column(Text, nullable=True)

    # Organization scope - content is only visible within this organization
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)

    # Author info
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Engagement metrics
    likes_count = Column(Integer, default=0)
    comments_count = Column(Integer, default=0)
    shares_count = Column(Integer, default=0)
    views_count = Column(Integer, default=0)

    # Status
    is_active = Column(Boolean, default=True)  # Soft delete support

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organization = relationship("Organization")
    author = relationship("User")

    # Composite index for efficient organization-scoped queries
    __table_args__ = (
        Index('ix_shared_diagrams_org_created', 'organization_id', 'created_at'),
        Index('ix_shared_diagrams_org_category', 'organization_id', 'category'),
    )


class SharedDiagramLike(Base):
    """
    Tracks user likes on shared diagrams.
    One like per user per diagram.
    """
    __tablename__ = "shared_diagram_likes"

    id = Column(Integer, primary_key=True, index=True)
    diagram_id = Column(String(36), ForeignKey("shared_diagrams.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    diagram = relationship("SharedDiagram")
    user = relationship("User")

    # Unique constraint: one like per user per diagram
    __table_args__ = (
        Index('ix_shared_diagram_likes_unique', 'diagram_id', 'user_id', unique=True),
    )


class SharedDiagramComment(Base):
    """
    Comments on shared diagrams.
    """
    __tablename__ = "shared_diagram_comments"

    id = Column(Integer, primary_key=True, index=True)
    diagram_id = Column(String(36), ForeignKey("shared_diagrams.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    content = Column(Text, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Status
    is_active = Column(Boolean, default=True)  # Soft delete support

    # Relationships
    diagram = relationship("SharedDiagram")
    user = relationship("User")
