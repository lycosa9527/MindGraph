"""Gewe Group Member Database Model.

Stores WeChat group member information for caching and faster access.

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


class GeweGroupMember(Base):
    """
    WeChat group member storage model.

    Similar to xxxbot-pad's group_members_db but uses PostgreSQL.
    Stores group member information for caching.
    """

    __tablename__ = "gewe_group_members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    app_id: Mapped[str] = mapped_column(String(40), index=True, nullable=False, comment="Gewe app ID")
    group_wxid: Mapped[str] = mapped_column(String(40), index=True, nullable=False, comment="Group wxid")
    member_wxid: Mapped[str] = mapped_column(String(40), index=True, nullable=False, comment="Member wxid")
    nickname: Mapped[str | None] = mapped_column(String(200), nullable=True, comment="Member nickname")
    display_name: Mapped[str | None] = mapped_column(String(200), nullable=True, comment="Display name in group")
    avatar: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Avatar URL")
    inviter_wxid: Mapped[str | None] = mapped_column(String(40), nullable=True, comment="Who invited this member")
    join_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="Join time")
    last_updated: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
        comment="Last update timestamp",
    )
    extra_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True, comment="Additional structured data")

    # Composite unique constraint: same member can only exist once per group per app
    __table_args__ = (
        Index("idx_app_group_member", "app_id", "group_wxid", "member_wxid", unique=True),
        Index("idx_app_group", "app_id", "group_wxid"),
        Index("idx_app_member", "app_id", "member_wxid"),
    )
