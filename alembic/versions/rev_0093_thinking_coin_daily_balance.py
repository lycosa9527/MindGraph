"""Thinking coin daily login balance that expires at Beijing midnight.

Revision ID: 0093
Revises: 0092
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0093"
down_revision: Union[str, None] = "0092"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("thinking_coin_wallets"):
        return

    columns = {col["name"] for col in inspector.get_columns("thinking_coin_wallets")}
    if "daily_balance" not in columns:
        op.add_column(
            "thinking_coin_wallets",
            sa.Column(
                "daily_balance",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
        )
    if "daily_balance_date" not in columns:
        op.add_column(
            "thinking_coin_wallets",
            sa.Column("daily_balance_date", sa.Date(), nullable=True),
        )

    existing_checks = {ck["name"] for ck in inspector.get_check_constraints("thinking_coin_wallets")}
    if "ck_thinking_coin_wallets_daily_nonneg" not in existing_checks:
        op.create_check_constraint(
            "ck_thinking_coin_wallets_daily_nonneg",
            "thinking_coin_wallets",
            "daily_balance >= 0",
        )
    if "ck_thinking_coin_wallets_daily_lte_balance" not in existing_checks:
        op.create_check_constraint(
            "ck_thinking_coin_wallets_daily_lte_balance",
            "thinking_coin_wallets",
            "daily_balance <= balance",
        )

    if inspector.has_table("thinking_coin_earn_tasks"):
        op.execute(
            sa.text(
                "UPDATE thinking_coin_earn_tasks "
                "SET subtitle = '登录即领，当日有效，24:00清零', "
                "subtitle_en = 'Claim on login; expires at midnight' "
                "WHERE slug = 'daily_checkin'"
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("thinking_coin_wallets"):
        return

    existing_checks = {ck["name"] for ck in inspector.get_check_constraints("thinking_coin_wallets")}
    if "ck_thinking_coin_wallets_daily_lte_balance" in existing_checks:
        op.drop_constraint(
            "ck_thinking_coin_wallets_daily_lte_balance",
            "thinking_coin_wallets",
            type_="check",
        )
    if "ck_thinking_coin_wallets_daily_nonneg" in existing_checks:
        op.drop_constraint(
            "ck_thinking_coin_wallets_daily_nonneg",
            "thinking_coin_wallets",
            type_="check",
        )

    columns = {col["name"] for col in inspector.get_columns("thinking_coin_wallets")}
    if "daily_balance_date" in columns:
        op.drop_column("thinking_coin_wallets", "daily_balance_date")
    if "daily_balance" in columns:
        op.drop_column("thinking_coin_wallets", "daily_balance")

    if inspector.has_table("thinking_coin_earn_tasks"):
        op.execute(
            sa.text(
                "UPDATE thinking_coin_earn_tasks "
                "SET subtitle = '登录即领取', "
                "subtitle_en = 'Claim on login' "
                "WHERE slug = 'daily_checkin'"
            )
        )
