"""
Diagram Snapshot Models for MindGraph
======================================

Versioned snapshots of diagram specs for point-in-time restore.
Max 10 snapshots per diagram; oldest is evicted when the limit is reached.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects import postgresql as pg
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.domain.auth import Base


class DiagramSnapshot(Base):
    """
    A versioned snapshot of a diagram's spec.

    Each row is an immutable copy of the diagram spec at the moment the user
    clicked "Snapshot".  Snapshots are numbered 1..N (max 10).  When the 11th
    is taken, version 1 is deleted and the remaining rows are renumbered
    2→1, 3→2, … so numbering is always gap-free.

    LLM results are intentionally excluded — only the diagram content is stored.
    """

    __tablename__ = "diagram_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    diagram_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("diagrams.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    spec: Mapped[dict] = mapped_column(pg.JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    diagram: Mapped["Diagram"] = relationship("Diagram", back_populates="snapshots", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("diagram_id", "version_number", name="uq_diagram_snapshot_version"),
        Index("ix_diagram_snapshots_diagram_version", "diagram_id", "version_number"),
    )

    def __repr__(self) -> str:
        return f"<DiagramSnapshot diagram={self.diagram_id} v{self.version_number}>"
