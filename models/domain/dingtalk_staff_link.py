"""
DingTalk staff id to MindGraph user binding for MindBot library save.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.domain.auth import Base


class DingtalkStaffLink(Base):
    """Maps a DingTalk ``senderStaffId`` within an org to a MindGraph ``users.id``."""

    __tablename__ = "dingtalk_staff_links"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "dingtalk_staff_id",
            name="uq_dingtalk_staff_links_org_staff",
        ),
        UniqueConstraint(
            "organization_id",
            "user_id",
            name="uq_dingtalk_staff_links_org_user",
        ),
        Index("ix_dingtalk_staff_links_user_org", "user_id", "organization_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    dingtalk_staff_id: Mapped[str] = mapped_column(String(128), nullable=False)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    linked_via: Mapped[str] = mapped_column(String(32), nullable=False, default="qr_bind")
    linked_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    user = relationship("User", foreign_keys=[user_id], lazy="select")

    def __repr__(self) -> str:
        return (
            f"<DingtalkStaffLink org={self.organization_id} "
            f"staff={self.dingtalk_staff_id!r} user_id={self.user_id}>"
        )
