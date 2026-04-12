"""MindBot usage: educational research columns.

Revision ID: 0012
Revises: 0011
Create Date: 2026-04-13
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "mindbot_usage_events",
        sa.Column("dingtalk_chat_scope", sa.String(length=16), nullable=True),
    )
    op.add_column(
        "mindbot_usage_events",
        sa.Column("inbound_msg_type", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "mindbot_usage_events",
        sa.Column("conversation_user_turn", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_mindbot_usage_events_chat_scope_org",
        "mindbot_usage_events",
        ["dingtalk_chat_scope", "organization_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_mindbot_usage_events_chat_scope_org",
        table_name="mindbot_usage_events",
    )
    op.drop_column("mindbot_usage_events", "conversation_user_turn")
    op.drop_column("mindbot_usage_events", "inbound_msg_type")
    op.drop_column("mindbot_usage_events", "dingtalk_chat_scope")
