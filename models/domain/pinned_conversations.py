from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship

from models.domain.auth import Base

"""
Pinned Conversations Model for MindGraph
Author: lycosa9527
Made by: MindSpring Team

Database model for tracking pinned MindMate conversations.
Since MindMate conversations are stored in Dify (external service),
we track pinned status in our own database.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""




class PinnedConversation(Base):
    """
    Tracks pinned MindMate conversations for users.

    Each record represents a pinned conversation for a specific user.
    The conversation_id references the Dify conversation ID (UUID string).
    """
    __tablename__ = "pinned_conversations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    conversation_id = Column(String(36), nullable=False, index=True)
    pinned_at = Column(DateTime, default=datetime.utcnow)

    # Relationship
    user = relationship("User", backref="pinned_conversations")

    # Composite unique constraint: one pin per user per conversation
    __table_args__ = (
        Index('ix_pinned_conv_user_conv', 'user_id', 'conversation_id', unique=True),
    )
