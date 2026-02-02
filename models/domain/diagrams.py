"""
Diagram Storage Models for MindGraph
=====================================

Database model for user-created diagrams with persistent storage.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from datetime import datetime
import uuid

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Index
from sqlalchemy.orm import relationship

from models.domain.auth import Base


def generate_uuid():
    """Generate a UUID string for diagram IDs."""
    return str(uuid.uuid4())


class Diagram(Base):
    """
    User-created diagrams for persistent storage and editing.

    Stores the complete diagram spec as JSON text for flexibility.
    Supports soft delete for data recovery.
    Uses UUID for secure, non-guessable diagram IDs.
    """
    __tablename__ = "diagrams"

    id = Column(String(36), primary_key=True, default=generate_uuid, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Metadata (queryable)
    title = Column(String(200), nullable=False)
    diagram_type = Column(String(50), nullable=False, index=True)
    language = Column(String(10), default='zh')

    # The actual diagram data as JSON text
    spec = Column(Text, nullable=False)

    # Optional: thumbnail for gallery view (base64 data URL)
    thumbnail = Column(Text, nullable=True)

    # Soft delete support
    is_deleted = Column(Boolean, default=False, index=True)

    # Pin support - pinned diagrams appear at top
    is_pinned = Column(Boolean, default=False, index=True)

    # Workshop support - shareable code for collaborative editing
    workshop_code = Column(String(20), nullable=True, index=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    user = relationship("User", back_populates="diagrams")

    # Composite index for efficient queries
    __table_args__ = (
        Index('ix_diagrams_user_updated', 'user_id', 'updated_at', 'is_deleted'),
    )

    def __repr__(self):
        return f"<Diagram {self.id}: {self.title} ({self.diagram_type})>"
