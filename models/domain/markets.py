"""
Market (市场) catalog, orders, payments, entitlements, subscriptions.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from datetime import UTC, datetime
from typing import Any, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects import postgresql as pg
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.domain.auth import Base


class MarketListing(Base):
    """Sellable item: template, course package, or subscription plan SKU."""

    __tablename__ = "market_listings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    listing_kind: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True
    )  # template | course | subscription_plan
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    price_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="CNY", nullable=False)
    product_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    scene: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    subject: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    spec_json: Mapped[Optional[dict[str, Any]]] = mapped_column(pg.JSONB, nullable=True)
    extra_json: Mapped[Optional[dict[str, Any]]] = mapped_column(pg.JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    orders: Mapped[list["MarketOrder"]] = relationship("MarketOrder", back_populates="listing", lazy="selectin")


class MarketOrder(Base):
    """User order for one listing (single-item checkout)."""

    __tablename__ = "market_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    listing_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("market_listings.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    out_trade_no: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)  # pending | paid | closed | cancelled
    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="CNY", nullable=False)
    alipay_trade_no: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    user: Mapped["User"] = relationship("User", lazy="selectin")
    listing: Mapped["MarketListing"] = relationship("MarketListing", back_populates="orders", lazy="selectin")
    payment: Mapped[Optional["MarketPayment"]] = relationship(
        "MarketPayment",
        back_populates="order",
        uselist=False,
        lazy="selectin",
    )

    __table_args__ = (Index("ix_market_orders_user_created", "user_id", "created_at"),)


class MarketPayment(Base):
    """Alipay payment record linked to an order (idempotent notify)."""

    __tablename__ = "market_payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("market_orders.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )
    notify_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    trade_no: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    order: Mapped["MarketOrder"] = relationship("MarketOrder", back_populates="payment", lazy="selectin")


class MarketEntitlement(Base):
    """Granted access after successful payment."""

    __tablename__ = "market_entitlements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user: Mapped["User"] = relationship("User", lazy="selectin")
    listing_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("market_listings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    order_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("market_orders.id", ondelete="SET NULL"), nullable=True
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    __table_args__ = (UniqueConstraint("user_id", "listing_id", name="uq_market_entitlements_user_listing"),)


class MarketSubscription(Base):
    """Periodic agreement / subscription state (Alipay agreement id stored when live)."""

    __tablename__ = "market_subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user: Mapped["User"] = relationship("User", lazy="selectin")
    listing_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("market_listings.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    listing: Mapped["MarketListing"] = relationship("MarketListing", lazy="selectin")
    alipay_agreement_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False, index=True)
    current_period_end: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (Index("ix_market_subscriptions_user_listing", "user_id", "listing_id"),)
