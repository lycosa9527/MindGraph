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

from datetime import UTC, datetime
import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.domain.auth import Base

if TYPE_CHECKING:
    from models.domain.auth import User


def generate_uuid() -> str:
    """Generate a UUID string for debate session IDs."""
    return str(uuid.uuid4())


class DebateSession(Base):
    """
    Debate session model.

    Stores debate metadata including topic, format, current stage, and status.
    """

    __tablename__ = "debate_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    topic: Mapped[str] = mapped_column(String(500), nullable=False)
    format: Mapped[str] = mapped_column(String(50), default="us_parliamentary")

    current_stage: Mapped[str] = mapped_column(String(50), default="setup", index=True)

    status: Mapped[str] = mapped_column(String(50), default="pending", index=True)

    coin_toss_result: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    user: Mapped["User"] = relationship("User", backref="debate_sessions", lazy="selectin")
    participants: Mapped[list["DebateParticipant"]] = relationship(
        "DebateParticipant",
        back_populates="session",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    messages: Mapped[list["DebateMessage"]] = relationship(
        "DebateMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    judgment: Mapped[Optional["DebateJudgment"]] = relationship(
        "DebateJudgment",
        back_populates="session",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        Index("ix_debate_sessions_user_updated", "user_id", "updated_at", "status"),
        Index("ix_debate_sessions_stage_status", "current_stage", "status"),
    )

    def __repr__(self) -> str:
        return f"<DebateSession {self.id}: {self.topic[:30]}... ({self.current_stage})>"


class DebateParticipant(Base):
    """
    Debate participant model.

    Links users or AI models to debate sessions with specific roles.
    """

    __tablename__ = "debate_participants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("debate_sessions.id"), nullable=False, index=True)

    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    is_ai: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    role: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    side: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    model_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    name: Mapped[str] = mapped_column(String(100), nullable=False)

    joined_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    session: Mapped["DebateSession"] = relationship(
        "DebateSession",
        back_populates="participants",
        lazy="selectin",
    )
    user: Mapped[Optional["User"]] = relationship("User", backref="debate_participations", lazy="selectin")
    messages: Mapped[list["DebateMessage"]] = relationship(
        "DebateMessage",
        back_populates="participant",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (Index("ix_debate_participants_session_role", "session_id", "role"),)

    def __repr__(self) -> str:
        return f"<DebateParticipant {self.id}: {self.name} ({self.role})>"


class DebateMessage(Base):
    """
    Debate message model.

    Stores all messages in a debate including content, thinking, stage, and audio.
    """

    __tablename__ = "debate_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("debate_sessions.id"), nullable=False, index=True)
    participant_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("debate_participants.id"),
        nullable=False,
        index=True,
    )

    content: Mapped[str] = mapped_column(Text, nullable=False)
    thinking: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    stage: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    round_number: Mapped[int] = mapped_column(Integer, default=1, index=True)

    message_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    parent_message_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("debate_messages.id"), nullable=True)

    audio_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), index=True)

    session: Mapped["DebateSession"] = relationship("DebateSession", back_populates="messages", lazy="selectin")
    participant: Mapped["DebateParticipant"] = relationship(
        "DebateParticipant",
        back_populates="messages",
        lazy="selectin",
    )
    parent_message: Mapped[Optional["DebateMessage"]] = relationship(
        "DebateMessage",
        remote_side=[id],
        backref="child_messages",
        lazy="selectin",
    )

    __table_args__ = (
        Index("ix_debate_messages_session_stage", "session_id", "stage", "round_number"),
        Index("ix_debate_messages_session_created", "session_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<DebateMessage {self.id}: {self.message_type} ({self.stage})>"


class DebateJudgment(Base):
    """
    Debate judgment model.

    Stores judge's final evaluation, scores, and detailed analysis.
    """

    __tablename__ = "debate_judgments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("debate_sessions.id"),
        nullable=False,
        unique=True,
        index=True,
    )
    judge_participant_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("debate_participants.id"),
        nullable=False,
        index=True,
    )

    winner_side: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    best_debater_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("debate_participants.id"), nullable=True)

    scores: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    detailed_analysis: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    session: Mapped["DebateSession"] = relationship("DebateSession", back_populates="judgment", lazy="selectin")
    judge: Mapped["DebateParticipant"] = relationship(
        "DebateParticipant",
        foreign_keys=[judge_participant_id],
        backref="judgments_made",
        lazy="selectin",
    )
    best_debater: Mapped[Optional["DebateParticipant"]] = relationship(
        "DebateParticipant",
        foreign_keys=[best_debater_id],
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<DebateJudgment {self.id}: Winner={self.winner_side}>"
