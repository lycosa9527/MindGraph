"""
Diagram archive folders for organizing saved diagrams.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
import uuid

from sqlalchemy import ForeignKey, Index, Integer, String, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.domain.auth import Base

if TYPE_CHECKING:
    from models.domain.auth import User
    from models.domain.diagrams import Diagram


def generate_folder_uuid() -> str:
    """Generate a UUID string for diagram folder IDs."""
    return str(uuid.uuid4())


class DiagramFolder(Base):
    """User-owned folder for archiving / organizing saved diagrams."""

    __tablename__ = "diagram_folders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_folder_uuid)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    user: Mapped["User"] = relationship("User", back_populates="diagram_folders", lazy="selectin")
    diagrams: Mapped[list["Diagram"]] = relationship(
        "Diagram",
        back_populates="folder",
        lazy="selectin",
    )

    __table_args__ = (Index("ix_diagram_folders_user_sort", "user_id", "sort_order"),)

    def __repr__(self) -> str:
        return f"<DiagramFolder {self.id}: {self.name}>"
