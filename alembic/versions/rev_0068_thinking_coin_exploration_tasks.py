"""Seed exploration earn tasks and raise daily earn cap."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision: str = "0068"
down_revision: Union[str, None] = "0067"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add client_event exploration tasks; daily cap 100 (60 core + 35 explore)."""
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE thinking_coin_settings SET value_int = 100 "
            "WHERE key = 'daily_earn_cap'"
        )
    )
    missing = conn.execute(
        sa.text("SELECT 1 FROM thinking_coin_settings WHERE key = 'daily_earn_cap'")
    ).scalar()
    if missing is None:
        conn.execute(
            sa.text(
                "INSERT INTO thinking_coin_settings (key, value_int, value_text) "
                "VALUES ('daily_earn_cap', 100, NULL)"
            )
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
                "slug": "daily_mindmate_share",
                "title": "分享 MindMate 对话",
                "subtitle": "导出分享图一次",
                "title_en": "Share MindMate chat",
                "subtitle_en": "Export a share image once today",
                "reward_amount": 10,
                "monthly_cap": None,
                "handler_key": "client_event",
                "action_config": {"event_key": "mindmate_share"},
                "sort_order": 35,
                "is_active": True,
                "is_system": True,
            },
            {
                "slug": "daily_diagram_export",
                "title": "导出导图",
                "subtitle": "PNG / PDF / SVG 等任一格式",
                "title_en": "Export a diagram",
                "subtitle_en": "Any export format once today",
                "reward_amount": 10,
                "monthly_cap": None,
                "handler_key": "client_event",
                "action_config": {"event_key": "diagram_export"},
                "sort_order": 36,
                "is_active": True,
                "is_system": True,
            },
            {
                "slug": "daily_learning_sheet",
                "title": "使用半成品图示",
                "subtitle": "开启学习单/挖空模式",
                "title_en": "Use learning sheet",
                "subtitle_en": "Enable blanks mode once today",
                "reward_amount": 10,
                "monthly_cap": None,
                "handler_key": "client_event",
                "action_config": {"event_key": "learning_sheet_enable"},
                "sort_order": 37,
                "is_active": True,
                "is_system": True,
            },
            {
                "slug": "daily_diagram_save",
                "title": "保存导图",
                "subtitle": "首次保存到云端",
                "title_en": "Save a diagram",
                "subtitle_en": "First cloud save today",
                "reward_amount": 5,
                "monthly_cap": None,
                "handler_key": "client_event",
                "action_config": {"event_key": "diagram_save"},
                "sort_order": 38,
                "is_active": True,
                "is_system": True,
            },
        ],
    )


def downgrade() -> None:
    """Remove exploration tasks."""
    op.execute(
        sa.text(
            "DELETE FROM thinking_coin_earn_tasks WHERE slug IN ("
            "'daily_mindmate_share', 'daily_diagram_export', "
            "'daily_learning_sheet', 'daily_diagram_save')"
        )
    )
