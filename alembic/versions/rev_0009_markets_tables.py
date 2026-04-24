"""Market (市场) catalog, orders, payments, entitlements, subscriptions.

Baseline revision ``0001`` runs ``Base.metadata.create_all``; that may already
create the market tables. Skip ``CREATE TABLE`` (and per-table indexes) when
each relation already exists, matching ``0005`` / ``user_api_tokens``.

Revision ID: 0009
Revises: 0008
Create Date: 2026-04-11
"""

from datetime import UTC, datetime
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if not _has_table("market_listings"):
        op.create_table(
            "market_listings",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("slug", sa.String(length=64), nullable=False),
            sa.Column("listing_kind", sa.String(length=32), nullable=False),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("price_minor", sa.Integer(), nullable=False),
            sa.Column("currency", sa.String(length=10), nullable=False),
            sa.Column("product_type", sa.String(length=32), nullable=True),
            sa.Column("scene", sa.String(length=64), nullable=True),
            sa.Column("subject", sa.String(length=64), nullable=True),
            sa.Column("spec_json", pg.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("extra_json", pg.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("slug"),
        )
        op.create_index("ix_market_listings_slug", "market_listings", ["slug"], unique=False)
        op.create_index("ix_market_listings_listing_kind", "market_listings", ["listing_kind"], unique=False)
        op.create_index("ix_market_listings_product_type", "market_listings", ["product_type"], unique=False)
        op.create_index("ix_market_listings_scene", "market_listings", ["scene"], unique=False)
        op.create_index("ix_market_listings_subject", "market_listings", ["subject"], unique=False)
        op.create_index("ix_market_listings_is_active", "market_listings", ["is_active"], unique=False)

    if not _has_table("market_orders"):
        op.create_table(
            "market_orders",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("listing_id", sa.Integer(), nullable=False),
            sa.Column("out_trade_no", sa.String(length=64), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("amount_minor", sa.Integer(), nullable=False),
            sa.Column("currency", sa.String(length=10), nullable=False),
            sa.Column("alipay_trade_no", sa.String(length=64), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("paid_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["listing_id"], ["market_listings.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("out_trade_no"),
        )
        op.create_index("ix_market_orders_user_id", "market_orders", ["user_id"], unique=False)
        op.create_index("ix_market_orders_listing_id", "market_orders", ["listing_id"], unique=False)
        op.create_index("ix_market_orders_out_trade_no", "market_orders", ["out_trade_no"], unique=False)
        op.create_index("ix_market_orders_status", "market_orders", ["status"], unique=False)
        op.create_index("ix_market_orders_alipay_trade_no", "market_orders", ["alipay_trade_no"], unique=False)
        op.create_index("ix_market_orders_user_created", "market_orders", ["user_id", "created_at"], unique=False)

    if not _has_table("market_payments"):
        op.create_table(
            "market_payments",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("order_id", sa.Integer(), nullable=False),
            sa.Column("notify_id", sa.String(length=128), nullable=True),
            sa.Column("trade_no", sa.String(length=64), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["order_id"], ["market_orders.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("order_id"),
        )
        op.create_index("ix_market_payments_order_id", "market_payments", ["order_id"], unique=False)
        op.create_index("ix_market_payments_notify_id", "market_payments", ["notify_id"], unique=False)
        op.create_index("ix_market_payments_trade_no", "market_payments", ["trade_no"], unique=False)

    if not _has_table("market_entitlements"):
        op.create_table(
            "market_entitlements",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("listing_id", sa.Integer(), nullable=False),
            sa.Column("order_id", sa.Integer(), nullable=True),
            sa.Column("expires_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["listing_id"], ["market_listings.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["order_id"], ["market_orders.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "listing_id", name="uq_market_entitlements_user_listing"),
        )
        op.create_index("ix_market_entitlements_user_id", "market_entitlements", ["user_id"], unique=False)
        op.create_index("ix_market_entitlements_listing_id", "market_entitlements", ["listing_id"], unique=False)
        op.create_index("ix_market_entitlements_expires_at", "market_entitlements", ["expires_at"], unique=False)

    if not _has_table("market_subscriptions"):
        op.create_table(
            "market_subscriptions",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("listing_id", sa.Integer(), nullable=False),
            sa.Column("alipay_agreement_id", sa.String(length=128), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("current_period_end", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["listing_id"], ["market_listings.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_market_subscriptions_user_id", "market_subscriptions", ["user_id"], unique=False)
        op.create_index("ix_market_subscriptions_listing_id", "market_subscriptions", ["listing_id"], unique=False)
        op.create_index(
            "ix_market_subscriptions_alipay_agreement_id", "market_subscriptions", ["alipay_agreement_id"],
            unique=False,
        )
        op.create_index("ix_market_subscriptions_status", "market_subscriptions", ["status"], unique=False)
        op.create_index(
            "ix_market_subscriptions_user_listing", "market_subscriptions", ["user_id", "listing_id"], unique=False
        )

    _seed_listings()


def _seed_listings() -> None:
    now = datetime.now(UTC).replace(tzinfo=None)
    rows = [
        {
            "slug": "demo-template-zh-primary",
            "listing_kind": "template",
            "title": "小学语文课文思维导图模板",
            "description": "Demo MindGraph template listing",
            "price_minor": 100,
            "currency": "CNY",
            "product_type": "MindGraph",
            "scene": "教学通用",
            "subject": "语文",
            "spec_json": None,
            "extra_json": None,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        },
        {
            "slug": "demo-template-math",
            "listing_kind": "template",
            "title": "初中数学公式整理思维导图",
            "description": "Demo MindGraph template listing",
            "price_minor": 200,
            "currency": "CNY",
            "product_type": "MindGraph",
            "scene": "总结汇报",
            "subject": "数学",
            "spec_json": None,
            "extra_json": None,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        },
        {
            "slug": "demo-course-thinking-intro",
            "listing_kind": "course",
            "title": "思维课程入门包（演示）",
            "description": "Demo course SKU",
            "price_minor": 9900,
            "currency": "CNY",
            "product_type": None,
            "scene": "教学通用",
            "subject": "综合实践",
            "spec_json": None,
            "extra_json": {"access_days": 90},
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        },
        {
            "slug": "demo-subscription-monthly",
            "listing_kind": "subscription_plan",
            "title": "市场月度会员（演示）",
            "description": "Demo subscription plan; wire Alipay agreement separately",
            "price_minor": 1990,
            "currency": "CNY",
            "product_type": None,
            "scene": None,
            "subject": None,
            "spec_json": None,
            "extra_json": {"interval": "month"},
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        },
    ]
    if not _has_table("market_listings"):
        return
    bind = op.get_bind()
    stmt = text(
        """
        INSERT INTO market_listings (
            slug, listing_kind, title, description, price_minor, currency,
            product_type, scene, subject, spec_json, extra_json, is_active, created_at, updated_at
        ) VALUES (
            :slug, :listing_kind, :title, :description, :price_minor, :currency,
            :product_type, :scene, :subject, :spec_json, :extra_json,
            :is_active, :created_at, :updated_at
        )
        ON CONFLICT (slug) DO NOTHING
        """
    )
    for row in rows:
        bind.execute(stmt, row)


def downgrade() -> None:
    for name in (
        "market_subscriptions",
        "market_entitlements",
        "market_payments",
        "market_orders",
        "market_listings",
    ):
        if _has_table(name):
            op.drop_table(name)
