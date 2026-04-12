"""MindBot usage events for DingTalk analytics.

Revision ID: 0011
Revises: 0010
Create Date: 2026-04-13
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "mindbot_usage_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("mindbot_config_id", sa.Integer(), nullable=True),
        sa.Column("dingtalk_staff_id", sa.String(length=128), nullable=False),
        sa.Column("sender_nick", sa.String(length=256), nullable=True),
        sa.Column("dingtalk_sender_id", sa.String(length=128), nullable=True),
        sa.Column("dify_user_key", sa.String(length=256), nullable=False),
        sa.Column("msg_id", sa.String(length=128), nullable=True),
        sa.Column("dingtalk_conversation_id", sa.String(length=256), nullable=True),
        sa.Column("dify_conversation_id", sa.String(length=128), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=False),
        sa.Column("streaming", sa.Boolean(), nullable=False),
        sa.Column("prompt_chars", sa.Integer(), nullable=False),
        sa.Column("reply_chars", sa.Integer(), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("linked_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["linked_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["mindbot_config_id"],
            ["organization_mindbot_configs.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_mindbot_usage_events_created_at",
        "mindbot_usage_events",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_mindbot_usage_events_msg_id",
        "mindbot_usage_events",
        ["msg_id"],
        unique=False,
    )
    op.create_index(
        "ix_mindbot_usage_events_organization_id",
        "mindbot_usage_events",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_mindbot_usage_events_mindbot_config_id",
        "mindbot_usage_events",
        ["mindbot_config_id"],
        unique=False,
    )
    op.create_index(
        "ix_mindbot_usage_events_linked_user_id",
        "mindbot_usage_events",
        ["linked_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_mindbot_usage_org_created",
        "mindbot_usage_events",
        ["organization_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_mindbot_usage_staff_org",
        "mindbot_usage_events",
        ["dingtalk_staff_id", "organization_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_mindbot_usage_staff_org", table_name="mindbot_usage_events")
    op.drop_index("ix_mindbot_usage_org_created", table_name="mindbot_usage_events")
    op.drop_index("ix_mindbot_usage_events_linked_user_id", table_name="mindbot_usage_events")
    op.drop_index("ix_mindbot_usage_events_mindbot_config_id", table_name="mindbot_usage_events")
    op.drop_index("ix_mindbot_usage_events_organization_id", table_name="mindbot_usage_events")
    op.drop_index("ix_mindbot_usage_events_msg_id", table_name="mindbot_usage_events")
    op.drop_index("ix_mindbot_usage_events_created_at", table_name="mindbot_usage_events")
    op.drop_table("mindbot_usage_events")
