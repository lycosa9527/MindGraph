"""Database models for per-feature organization and user access grants."""

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from models.domain.auth import Base


class FeatureAccessRule(Base):
    """
    One row per feature key (e.g. feature_workshop_chat).

    When restrict is False, all non-elevated users may use the feature (if the
    global FEATURE_* flag is on). When True, only listed org/user grants apply.
    """

    __tablename__ = "feature_access_rules"

    feature_key: Mapped[str] = mapped_column(String(80), primary_key=True)
    restrict: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )


class FeatureAccessOrgGrant(Base):
    """Organization allowed to use a feature when restrict=True."""

    __tablename__ = "feature_access_org_grants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    feature_key: Mapped[str] = mapped_column(
        String(80),
        ForeignKey("feature_access_rules.feature_key", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "feature_key",
            "organization_id",
            name="uq_feature_access_org_grant",
        ),
    )


class FeatureAccessUserGrant(Base):
    """User allowed to use a feature when restrict=True."""

    __tablename__ = "feature_access_user_grants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    feature_key: Mapped[str] = mapped_column(
        String(80),
        ForeignKey("feature_access_rules.feature_key", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "feature_key",
            "user_id",
            name="uq_feature_access_user_grant",
        ),
    )
