"""
Showcase admin models — staff grants, field options, audit log.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects import postgresql as pg
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.domain.auth import Base

if TYPE_CHECKING:
    from models.domain.auth import User


class ShowcaseStaffGrant(Base):
    """Per-user Showcase permissions (reviewers, proxy publishers, etc.)."""

    __tablename__ = "case_square_staff_grants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    permissions: Mapped[list] = mapped_column(pg.JSONB, nullable=False, default=list)
    granted_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id], lazy="selectin")
    granter: Mapped[Optional["User"]] = relationship("User", foreign_keys=[granted_by], lazy="selectin")

    __table_args__ = (UniqueConstraint("user_id", name="uq_case_square_staff_grants_user_id"),)


class ShowcaseFieldOption(Base):
    """Configurable subject / grade / recommended tag options."""

    __tablename__ = "case_square_field_options"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    value: Mapped[str] = mapped_column(String(100), nullable=False)
    label_zh: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    label_en: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        UniqueConstraint("category", "value", name="uq_case_square_field_options_category_value"),
        Index("ix_case_square_field_options_category_sort", "category", "sort_order"),
    )


class ShowcaseAuditLog(Base):
    """Audit trail for Showcase moderation actions."""

    __tablename__ = "case_square_audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    post_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    actor_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    payload: Mapped[Optional[dict]] = mapped_column(pg.JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        index=True,
    )
