"""B2C subscription columns: external agreement no, subscription links.

Revision ID: 0035
Revises: 0034
Create Date: 2026-05-22
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0035"
down_revision: Union[str, None] = "0034"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_names(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    sub_cols = _column_names("market_subscriptions") if sa.inspect(bind).has_table("market_subscriptions") else set()
    if "external_agreement_no" not in sub_cols and sub_cols:
        op.add_column(
            "market_subscriptions",
            sa.Column("external_agreement_no", sa.String(length=64), nullable=True),
        )
        op.create_index(
            "ix_market_subscriptions_external_agreement_no",
            "market_subscriptions",
            ["external_agreement_no"],
            unique=True,
        )
    if "started_at" not in sub_cols and sub_cols:
        op.add_column("market_subscriptions", sa.Column("started_at", sa.DateTime(), nullable=True))
    if "cancelled_at" not in sub_cols and sub_cols:
        op.add_column("market_subscriptions", sa.Column("cancelled_at", sa.DateTime(), nullable=True))

    order_cols = _column_names("market_orders") if sa.inspect(bind).has_table("market_orders") else set()
    if "subscription_id" not in order_cols and order_cols:
        op.add_column("market_orders", sa.Column("subscription_id", sa.Integer(), nullable=True))
        op.create_foreign_key(
            "fk_market_orders_subscription_id",
            "market_orders",
            "market_subscriptions",
            ["subscription_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index("ix_market_orders_subscription_id", "market_orders", ["subscription_id"], unique=False)

    ent_cols = _column_names("market_entitlements") if sa.inspect(bind).has_table("market_entitlements") else set()
    if "subscription_id" not in ent_cols and ent_cols:
        op.add_column("market_entitlements", sa.Column("subscription_id", sa.Integer(), nullable=True))
        op.create_foreign_key(
            "fk_market_entitlements_subscription_id",
            "market_entitlements",
            "market_subscriptions",
            ["subscription_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index(
            "ix_market_entitlements_subscription_id",
            "market_entitlements",
            ["subscription_id"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    if sa.inspect(bind).has_table("market_entitlements"):
        ent_cols = _column_names("market_entitlements")
        if "subscription_id" in ent_cols:
            op.drop_index("ix_market_entitlements_subscription_id", table_name="market_entitlements")
            op.drop_constraint("fk_market_entitlements_subscription_id", "market_entitlements", type_="foreignkey")
            op.drop_column("market_entitlements", "subscription_id")

    if sa.inspect(bind).has_table("market_orders"):
        order_cols = _column_names("market_orders")
        if "subscription_id" in order_cols:
            op.drop_index("ix_market_orders_subscription_id", table_name="market_orders")
            op.drop_constraint("fk_market_orders_subscription_id", "market_orders", type_="foreignkey")
            op.drop_column("market_orders", "subscription_id")

    if sa.inspect(bind).has_table("market_subscriptions"):
        sub_cols = _column_names("market_subscriptions")
        if "cancelled_at" in sub_cols:
            op.drop_column("market_subscriptions", "cancelled_at")
        if "started_at" in sub_cols:
            op.drop_column("market_subscriptions", "started_at")
        if "external_agreement_no" in sub_cols:
            op.drop_index("ix_market_subscriptions_external_agreement_no", table_name="market_subscriptions")
            op.drop_column("market_subscriptions", "external_agreement_no")
