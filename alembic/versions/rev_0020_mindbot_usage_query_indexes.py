"""MindBot: indexes for usage list/thread queries.

Revision ID: 0020
Revises: 0019
Create Date: 2026-04-16
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0020"
down_revision: Union[str, None] = "0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_mindbot_usage_org_id_desc",
        "mindbot_usage_events",
        ["organization_id", "id"],
    )
    op.create_index(
        "ix_mindbot_usage_dt_conv",
        "mindbot_usage_events",
        ["dingtalk_conversation_id"],
    )
    op.create_index(
        "ix_mindbot_usage_dify_conv",
        "mindbot_usage_events",
        ["dify_conversation_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_mindbot_usage_dify_conv", table_name="mindbot_usage_events")
    op.drop_index("ix_mindbot_usage_dt_conv", table_name="mindbot_usage_events")
    op.drop_index("ix_mindbot_usage_org_id_desc", table_name="mindbot_usage_events")
