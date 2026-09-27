"""
User avatar menu entries configured in system settings.

Each row is one function in the signed-in user dropdown. It can point at a
training course so the menu opens that course as a walkthrough.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.domain.auth import Base

if TYPE_CHECKING:
    from models.domain.training import TrainingCourse


def generate_user_dropdown_id() -> str:
    """Generate a UUID string for a dropdown row."""
    return str(uuid.uuid4())


class UserDropdownItem(Base):
    """One named function in the user avatar dropdown."""

    __tablename__ = "user_dropdown_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_user_dropdown_id)
    label: Mapped[str] = mapped_column(String(40), nullable=False)
    course_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("training_courses.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    course: Mapped[Optional["TrainingCourse"]] = relationship("TrainingCourse", lazy="selectin")
