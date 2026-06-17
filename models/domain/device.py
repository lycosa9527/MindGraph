"""
Device Model for ESP32 Smart Response Watches

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.domain.auth import Base

if TYPE_CHECKING:
    from models.domain.auth import User


class Device(Base):
    """ESP32 Watch Device Model"""

    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    watch_id: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    mac_address: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    student_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    status: Mapped[str] = mapped_column(String, default="unassigned")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    last_seen: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    student: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[student_id],
        backref="devices",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Device(watch_id='{self.watch_id}', status='{self.status}')>"
