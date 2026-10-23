"""
Canvas input profile for one browser device.

The row is keyed by the ``mg_device`` cookie, so a classroom board keeps
its mode for every account that signs in on that machine.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from models.domain.auth import Base

CANVAS_INPUT_MODES = ("mouse", "laptop", "mobile", "board")


class CanvasInputDevice(Base):
    """One browser's canvas gesture profile."""

    __tablename__ = "canvas_input_devices"

    device_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    input_mode: Mapped[str] = mapped_column(String(16), nullable=False)
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
