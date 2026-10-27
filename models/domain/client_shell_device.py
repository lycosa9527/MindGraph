"""
Mobile or desktop shell for one browser device.

The row is keyed by the ``mg_device`` cookie. A classroom tablet keeps the
choice the signed-in user made, including after the screen rotates and after
another account signs in on that same browser.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from models.domain.auth import Base

CLIENT_SHELLS = ("mobile", "desktop")


class ClientShellDevice(Base):
    """One browser's locked interface: mobile or desktop."""

    __tablename__ = "client_shell_devices"
    __table_args__ = (
        CheckConstraint(
            "shell IN ('mobile', 'desktop')",
            name="ck_client_shell_devices_shell",
        ),
    )

    device_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    shell: Mapped[str] = mapped_column(String(16), nullable=False)
    updated_by_user_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
