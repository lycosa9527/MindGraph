"""
Persisted 一句话生成 (one-sentence panel) sessions and turns.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from models.domain.auth import Base


class KittyOneSentenceSession(Base):
    """Trackable one-sentence panel session keyed by diagram scope (Kitty WS scope)."""

    __tablename__ = "kitty_one_sentence_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
    )
    diagram_scope: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    diagram_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("diagrams.id", ondelete="SET NULL"),
        nullable=True,
    )
    diagram_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    turn_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    create_turn_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    edit_turn_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    first_prompt_preview: Mapped[str | None] = mapped_column(String(120), nullable=True)
    last_voice_session_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "diagram_scope",
            name="uq_kitty_one_sentence_session_user_scope",
        ),
        Index("ix_kitty_one_sentence_sessions_user_activity", "user_id", "last_activity_at"),
        Index("ix_kitty_one_sentence_sessions_org_activity", "organization_id", "last_activity_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<KittyOneSentenceSession id={self.id!r} scope={self.diagram_scope!r} "
            f"user={self.user_id} turns={self.turn_count}>"
        )


class KittyOneSentenceTurn(Base):
    """One chat turn in the Kitty one-sentence panel scoped to a diagram session."""

    __tablename__ = "kitty_one_sentence_turns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("kitty_one_sentence_sessions.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
    )
    scope: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    turn_id: Mapped[str] = mapped_column(String(64), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    phase: Mapped[str] = mapped_column(String(16), nullable=False, default="edit")
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    action: Mapped[str | None] = mapped_column(String(64), nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(32), nullable=True)
    user_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    diagram_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    voice_session_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        UniqueConstraint("scope", "turn_id", name="uq_kitty_one_sentence_turn_scope_turn"),
        Index("ix_kitty_one_sentence_turns_scope_created", "scope", "created_at"),
        Index("ix_kitty_one_sentence_turns_user_created", "user_id", "created_at"),
        Index("ix_kitty_one_sentence_turns_session_created", "session_id", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<KittyOneSentenceTurn session={self.session_id!r} scope={self.scope!r} "
            f"role={self.role!r} phase={self.phase!r} id={self.id}>"
        )
