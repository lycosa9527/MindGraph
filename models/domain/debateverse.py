"""
DebateVerse Models for MindGraph
=================================

Database models for debate sessions, participants, messages, and judgments.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from datetime import datetime
import uuid

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Index, JSON
from sqlalchemy.orm import relationship

from models.domain.auth import Base



def generate_uuid():
    """Generate a UUID string for debate session IDs."""
    return str(uuid.uuid4())


class DebateSession(Base):
    """
    Debate session model.

    Stores debate metadata including topic, format, current stage, and status.
    """
    __tablename__ = "debate_sessions"

    id = Column(String(36), primary_key=True, default=generate_uuid, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Debate metadata
    topic = Column(String(500), nullable=False)
    format = Column(String(50), default='us_parliamentary')  # Debate format

    # Stage management
    current_stage = Column(String(50), default='setup', index=True)
    # Stages: setup, coin_toss, opening, rebuttal, cross_exam, closing, judgment, completed

    # Status
    status = Column(String(50), default='pending', index=True)
    # Status: pending, active, completed, cancelled

    # Coin toss result (if completed)
    coin_toss_result = Column(String(50), nullable=True)  # 'affirmative_first' or 'negative_first'

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", backref="debate_sessions")
    participants = relationship("DebateParticipant", back_populates="session", cascade="all, delete-orphan")
    messages = relationship("DebateMessage", back_populates="session", cascade="all, delete-orphan")
    judgment = relationship("DebateJudgment", back_populates="session", uselist=False, cascade="all, delete-orphan")

    # Composite index for efficient queries
    __table_args__ = (
        Index('ix_debate_sessions_user_updated', 'user_id', 'updated_at', 'status'),
        Index('ix_debate_sessions_stage_status', 'current_stage', 'status'),
    )

    def __repr__(self):
        return f"<DebateSession {self.id}: {self.topic[:30]}... ({self.current_stage})>"


class DebateParticipant(Base):
    """
    Debate participant model.

    Links users or AI models to debate sessions with specific roles.
    """
    __tablename__ = "debate_participants"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(36), ForeignKey("debate_sessions.id"), nullable=False, index=True)

    # Participant identification
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)  # Null for AI participants
    is_ai = Column(Boolean, default=False, index=True)

    # Role information
    role = Column(String(50), nullable=False, index=True)
    # Roles: affirmative_1, affirmative_2, negative_1, negative_2, judge, viewer

    side = Column(String(20), nullable=True)  # 'affirmative', 'negative', or None for judge/viewer

    # AI-specific fields
    model_id = Column(String(50), nullable=True)  # 'qwen', 'doubao', 'deepseek', 'kimi' for AI

    # Display name
    name = Column(String(100), nullable=False)  # User name or AI model display name

    # Timestamps
    joined_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    session = relationship("DebateSession", back_populates="participants")
    user = relationship("User", backref="debate_participations")
    messages = relationship("DebateMessage", back_populates="participant", cascade="all, delete-orphan")

    # Composite index
    __table_args__ = (
        Index('ix_debate_participants_session_role', 'session_id', 'role'),
    )

    def __repr__(self):
        return f"<DebateParticipant {self.id}: {self.name} ({self.role})>"


class DebateMessage(Base):
    """
    Debate message model.

    Stores all messages in a debate including content, thinking, stage, and audio.
    """
    __tablename__ = "debate_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(36), ForeignKey("debate_sessions.id"), nullable=False, index=True)
    participant_id = Column(Integer, ForeignKey("debate_participants.id"), nullable=False, index=True)

    # Message content
    content = Column(Text, nullable=False)
    thinking = Column(Text, nullable=True)  # Thinking/reasoning content for supported models

    # Stage and round information
    stage = Column(String(50), nullable=False, index=True)
    # Stages: coin_toss, opening, rebuttal, cross_exam, closing, judgment

    round_number = Column(Integer, default=1, index=True)  # Round within stage

    message_type = Column(String(50), nullable=False, index=True)
    # Types: coin_toss, opening, rebuttal, cross_question, cross_answer, closing, judgment

    # Cross-examination linking
    parent_message_id = Column(Integer, ForeignKey("debate_messages.id"), nullable=True)
    # For cross-exam: links question to answer

    # TTS audio
    audio_url = Column(String(500), nullable=True)  # URL to generated TTS audio

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    session = relationship("DebateSession", back_populates="messages")
    participant = relationship("DebateParticipant", back_populates="messages")
    parent_message = relationship("DebateMessage", remote_side=[id], backref="child_messages")

    # Composite indexes
    __table_args__ = (
        Index('ix_debate_messages_session_stage', 'session_id', 'stage', 'round_number'),
        Index('ix_debate_messages_session_created', 'session_id', 'created_at'),
    )

    def __repr__(self):
        return f"<DebateMessage {self.id}: {self.message_type} ({self.stage})>"


class DebateJudgment(Base):
    """
    Debate judgment model.

    Stores judge's final evaluation, scores, and detailed analysis.
    """
    __tablename__ = "debate_judgments"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(36), ForeignKey("debate_sessions.id"), nullable=False, unique=True, index=True)
    judge_participant_id = Column(Integer, ForeignKey("debate_participants.id"), nullable=False, index=True)

    # Verdict
    winner_side = Column(String(20), nullable=True)  # 'affirmative', 'negative', or None for tie
    best_debater_id = Column(Integer, ForeignKey("debate_participants.id"), nullable=True)

    # Scores (stored as JSON for flexibility)
    scores = Column(JSON, nullable=True)
    # Format: {
    #   "affirmative": {
    #     "logic": 8.5,
    #     "evidence": 7.0,
    #     "rebuttal": 9.0,
    #     "persuasiveness": 8.0,
    #     "total": 32.5
    #   },
    #   "negative": {...}
    # }

    # Detailed analysis
    detailed_analysis = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    session = relationship("DebateSession", back_populates="judgment")
    judge = relationship("DebateParticipant", foreign_keys=[judge_participant_id], backref="judgments_made")
    best_debater = relationship("DebateParticipant", foreign_keys=[best_debater_id])

    def __repr__(self):
        return f"<DebateJudgment {self.id}: Winner={self.winner_side}>"
