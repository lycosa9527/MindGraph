"""Gewe Contact Database Model.

Stores WeChat contact information for caching and faster access.

@author lycosa9527
@made_by MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .auth import Base


class GeweContact(Base):
    """
    WeChat contact storage model.

    Similar to xxxbot-pad's contacts_db but uses PostgreSQL.
    Stores contact information (friends, groups, official accounts) for caching.
    """

    __tablename__ = "gewe_contacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    app_id: Mapped[str] = mapped_column(String(40), index=True, nullable=False, comment="Gewe app ID")
    wxid: Mapped[str] = mapped_column(String(40), index=True, nullable=False, comment="Contact wxid (unique per app)")
    nickname: Mapped[str | None] = mapped_column(String(200), nullable=True, comment="Contact nickname")
    remark: Mapped[str | None] = mapped_column(String(200), nullable=True, comment="Contact remark")
    avatar: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Avatar URL")
    alias: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="WeChat alias")
    contact_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="friend",
        comment="Type: friend, group, official",
    )
    region: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="Region/location")
    last_updated: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
        comment="Last update timestamp",
    )
    extra_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True, comment="Additional structured data")

    # Composite unique constraint: same wxid can exist for different apps
    __table_args__ = (
        Index("idx_app_wxid", "app_id", "wxid", unique=True),
        Index("idx_app_type", "app_id", "contact_type"),
        Index("idx_app_nickname", "app_id", "nickname"),
    )
