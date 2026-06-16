"""Gewe Message Database Model.

Stores WeChat messages received via Gewe API for history and analysis.

@author lycosa9527
@made_by MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .auth import Base


class GeweMessage(Base):
    """
    WeChat message storage model.

    Similar to xxxbot-pad's Message model, but uses PostgreSQL.
    Stores all incoming WeChat messages for history tracking and analysis.
    """

    __tablename__ = "gewe_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    msg_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False, comment="Message unique ID (integer)")
    app_id: Mapped[str] = mapped_column(String(40), index=True, nullable=False, comment="Gewe app ID")
    sender_wxid: Mapped[str] = mapped_column(String(40), index=True, nullable=False, comment="Message sender wxid")
    from_wxid: Mapped[str] = mapped_column(String(40), index=True, nullable=False, comment="Message source wxid (chat)")
    msg_type: Mapped[int] = mapped_column(Integer, nullable=False, comment="Message type (integer code)")
    content: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Message content")
    timestamp: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC),
        index=True,
        nullable=False,
        comment="Message timestamp",
    )
    is_group: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, comment="Whether it is a group message"
    )

    # Composite indexes for common queries
    __table_args__ = (
        Index("idx_app_msg_id", "app_id", "msg_id"),
        Index("idx_app_from_timestamp", "app_id", "from_wxid", "timestamp"),
        Index("idx_app_sender_timestamp", "app_id", "sender_wxid", "timestamp"),
    )
