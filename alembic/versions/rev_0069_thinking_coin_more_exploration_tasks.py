"""Add translate, snapshot, workshop, and AI learning sheet earn tasks."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision: str = "0069"
down_revision: Union[str, None] = "0068"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Seed four exploration tasks; daily cap 135 (core 60 + explore 75)."""
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE thinking_coin_settings SET value_int = 135 "
            "WHERE key = 'daily_earn_cap'"
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
                "slug": "daily_diagram_translate",
                "title": "翻译导图",
                "subtitle": "今日首次一键翻译",
                "title_en": "Translate diagram",
                "subtitle_en": "First label translation today",
                "reward_amount": 10,
                "monthly_cap": None,
                "handler_key": "client_event",
                "action_config": {"event_key": "diagram_translate"},
                "sort_order": 39,
                "is_active": True,
                "is_system": True,
            },
            {
                "slug": "daily_diagram_snapshot",
                "title": "创建快照",
                "subtitle": "保存导图版本快照",
                "title_en": "Take a snapshot",
                "subtitle_en": "Save a diagram version snapshot",
                "reward_amount": 10,
                "monthly_cap": None,
                "handler_key": "client_event",
                "action_config": {"event_key": "diagram_snapshot"},
                "sort_order": 40,
                "is_active": True,
                "is_system": True,
            },
            {
                "slug": "daily_workshop_join",
                "title": "加入协作",
                "subtitle": "参与在线协作/演示",
                "title_en": "Join collaboration",
                "subtitle_en": "Join a live workshop session",
                "reward_amount": 10,
                "monthly_cap": None,
                "handler_key": "client_event",
                "action_config": {"event_key": "workshop_join"},
                "sort_order": 41,
                "is_active": True,
                "is_system": True,
            },
            {
                "slug": "daily_learning_sheet_ai",
                "title": "AI 生成半成品",
                "subtitle": "提示词含「半成品/学习单」",
                "title_en": "AI learning sheet",
                "subtitle_en": "Generate with learning-sheet prompt",
                "reward_amount": 10,
                "monthly_cap": None,
                "handler_key": "usage_daily",
                "action_config": {
                    "request_type": "diagram_generation",
                    "is_learning_sheet": True,
                },
                "sort_order": 42,
                "is_active": True,
                "is_system": True,
            },
        ],
    )


def downgrade() -> None:
    """Remove additional exploration tasks."""
    op.execute(
        sa.text(
            "DELETE FROM thinking_coin_earn_tasks WHERE slug IN ("
            "'daily_diagram_translate', 'daily_diagram_snapshot', "
            "'daily_workshop_join', 'daily_learning_sheet_ai')"
        )
    )
