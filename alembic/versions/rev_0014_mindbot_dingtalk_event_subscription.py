"""MindBot: DingTalk HTTP event subscription (callback URL verification) fields.

Revision ID: 0014
Revises: 0013
Create Date: 2026-04-13
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "organization_mindbot_configs",
        sa.Column("dingtalk_event_token", sa.Text(), nullable=True),
    )
    op.add_column(
        "organization_mindbot_configs",
        sa.Column("dingtalk_event_aes_key", sa.Text(), nullable=True),
    )
    op.add_column(
        "organization_mindbot_configs",
        sa.Column("dingtalk_event_owner_key", sa.String(length=128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("organization_mindbot_configs", "dingtalk_event_owner_key")
    op.drop_column("organization_mindbot_configs", "dingtalk_event_aes_key")
    op.drop_column("organization_mindbot_configs", "dingtalk_event_token")
