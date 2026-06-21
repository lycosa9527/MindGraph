"""Thinking coin wallet, ledger, earn tasks, and settings."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision: str = "0065"
down_revision: Union[str, None] = "0064"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if sa.inspect(bind).has_table("thinking_coin_wallets"):
        return

    op.create_table(
        "thinking_coin_wallets",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("balance", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("balance >= 0", name="ck_thinking_coin_wallets_balance_nonneg"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )

    op.create_table(
        "thinking_coin_ledger",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("delta", sa.Integer(), nullable=False),
        sa.Column("balance_after", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=32), nullable=False),
        sa.Column("ref_type", sa.String(length=32), nullable=True),
        sa.Column("ref_id", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_thinking_coin_ledger_user_id", "thinking_coin_ledger", ["user_id"])
    op.create_index("ix_thinking_coin_ledger_reason", "thinking_coin_ledger", ["reason"])
    op.create_index("ix_thinking_coin_ledger_created_at", "thinking_coin_ledger", ["created_at"])
    op.create_index(
        "ix_thinking_coin_ledger_user_created",
        "thinking_coin_ledger",
        ["user_id", "created_at"],
    )

    op.create_table(
        "thinking_coin_checkins",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("checkin_date", sa.Date(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "checkin_date", name="uq_thinking_coin_checkins_user_date"),
    )

    op.create_table(
        "thinking_coin_daily_activity",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("task_slug", sa.String(length=64), nullable=False),
        sa.Column("activity_date", sa.Date(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "task_slug",
            "activity_date",
            name="uq_thinking_coin_daily_activity_user_task_date",
        ),
    )

    op.create_table(
        "thinking_coin_earn_tasks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("subtitle", sa.String(length=300), nullable=True),
        sa.Column("title_en", sa.String(length=200), nullable=True),
        sa.Column("subtitle_en", sa.String(length=300), nullable=True),
        sa.Column("reward_amount", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("monthly_cap", sa.Integer(), nullable=True),
        sa.Column("handler_key", sa.String(length=32), nullable=False),
        sa.Column("action_config", pg.JSONB(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_thinking_coin_earn_tasks_slug", "thinking_coin_earn_tasks", ["slug"])

    op.create_table(
        "thinking_coin_settings",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("value_int", sa.Integer(), nullable=True),
        sa.Column("value_text", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("key"),
    )

    tasks_table = sa.table(
        "thinking_coin_earn_tasks",
        sa.column("slug", sa.String),
        sa.column("title", sa.String),
        sa.column("subtitle", sa.String),
        sa.column("title_en", sa.String),
        sa.column("subtitle_en", sa.String),
        sa.column("reward_amount", sa.Integer),
        sa.column("monthly_cap", sa.Integer),
        sa.column("handler_key", sa.String),
        sa.column("action_config", pg.JSONB),
        sa.column("sort_order", sa.Integer),
        sa.column("is_active", sa.Boolean),
        sa.column("is_system", sa.Boolean),
    )
    op.bulk_insert(
        tasks_table,
        [
            {
                "slug": "daily_checkin",
                "title": "每日签到",
                "subtitle": "登录即领取",
                "title_en": "Daily check-in",
                "subtitle_en": "Claim on login",
                "reward_amount": 25,
                "monthly_cap": None,
                "handler_key": "auto_login",
                "action_config": None,
                "sort_order": 10,
                "is_active": True,
                "is_system": True,
            },
            {
                "slug": "daily_mindmate",
                "title": "每日使用 MindMate",
                "subtitle": "今日首次对话",
                "title_en": "Daily MindMate",
                "subtitle_en": "First chat today",
                "reward_amount": 20,
                "monthly_cap": None,
                "handler_key": "usage_daily",
                "action_config": {"request_type": "mindmate"},
                "sort_order": 20,
                "is_active": True,
                "is_system": True,
            },
            {
                "slug": "daily_diagram_ai",
                "title": "每日 AI 制图",
                "subtitle": "今日首次生成导图",
                "title_en": "Daily AI diagram",
                "subtitle_en": "First diagram today",
                "reward_amount": 15,
                "monthly_cap": None,
                "handler_key": "usage_daily",
                "action_config": {"request_type": "diagram_generation"},
                "sort_order": 30,
                "is_active": True,
                "is_system": True,
            },
            {
                "slug": "referral_register",
                "title": "邀请好友注册",
                "subtitle": "即将开放",
                "title_en": "Invite friends",
                "subtitle_en": "Coming soon",
                "reward_amount": 100,
                "monthly_cap": 5,
                "handler_key": "copy_referral_link",
                "action_config": None,
                "sort_order": 40,
                "is_active": False,
                "is_system": True,
            },
            {
                "slug": "publish_case",
                "title": "发布案例",
                "subtitle": "审核通过后发放",
                "title_en": "Publish a case",
                "subtitle_en": "Reward after approval",
                "reward_amount": 30,
                "monthly_cap": 3,
                "handler_key": "navigate",
                "action_config": {"route": "/community", "icon": "document"},
                "sort_order": 50,
                "is_active": True,
                "is_system": True,
            },
        ],
    )

    settings_table = sa.table(
        "thinking_coin_settings",
        sa.column("key", sa.String),
        sa.column("value_int", sa.Integer),
        sa.column("value_text", sa.Text),
    )
    op.bulk_insert(
        settings_table,
        [
            {"key": "signup_grant", "value_int": 200, "value_text": None},
            {"key": "cost_mindmate_turn", "value_int": 6, "value_text": None},
            {"key": "cost_diagram_gen", "value_int": 15, "value_text": None},
            {"key": "cost_canvas_assist", "value_int": 4, "value_text": None},
        ],
    )


def downgrade() -> None:
    """Additive-only migration; downgrading risks dropping columns on legacy DBs."""
