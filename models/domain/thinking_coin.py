"""
Thinking coin (思维币) wallet, ledger, earn tasks, and settings.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects import postgresql as pg
from sqlalchemy.orm import Mapped, mapped_column

from models.domain.auth import Base


class ThinkingCoinWallet(Base):
    """Per-user thinking coin balance."""

    __tablename__ = "thinking_coin_wallets"

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    balance: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )

    __table_args__ = (CheckConstraint("balance >= 0", name="ck_thinking_coin_wallets_balance_nonneg"),)


class ThinkingCoinLedger(Base):
    """Append-only thinking coin transaction log."""

    __tablename__ = "thinking_coin_ledger"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    delta: Mapped[int] = mapped_column(Integer, nullable=False)
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    ref_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    ref_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        index=True,
    )

    __table_args__ = (Index("ix_thinking_coin_ledger_user_created", "user_id", "created_at"),)


class ThinkingCoinCheckin(Base):
    """Daily login check-in (Beijing calendar day)."""

    __tablename__ = "thinking_coin_checkins"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    checkin_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        UniqueConstraint("user_id", "checkin_date", name="uq_thinking_coin_checkins_user_date"),
    )


class ThinkingCoinDailyActivity(Base):
    """Idempotent daily usage earn (one row per user/task/day)."""

    __tablename__ = "thinking_coin_daily_activity"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    task_slug: Mapped[str] = mapped_column(String(64), nullable=False)
    activity_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "task_slug",
            "activity_date",
            name="uq_thinking_coin_daily_activity_user_task_date",
        ),
    )


class ThinkingCoinEarnTask(Base):
    """Admin-configurable earn task definitions."""

    __tablename__ = "thinking_coin_earn_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    subtitle: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    title_en: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    subtitle_en: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    reward_amount: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    monthly_cap: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    handler_key: Mapped[str] = mapped_column(String(32), nullable=False)
    action_config: Mapped[Optional[dict[str, Any]]] = mapped_column(pg.JSONB, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class ThinkingCoinSetting(Base):
    """Key-value global thinking coin configuration."""

    __tablename__ = "thinking_coin_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value_int: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    value_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
