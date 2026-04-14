"""MindBot: optional DingTalk AI card template for OpenAPI streaming replies.

Revision ID: 0018
Revises: 0017
Create Date: 2026-04-14
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: Union[str, None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "organization_mindbot_configs",
        sa.Column("dingtalk_ai_card_template_id", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "organization_mindbot_configs",
        sa.Column("dingtalk_ai_card_param_key", sa.String(length=128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("organization_mindbot_configs", "dingtalk_ai_card_param_key")
    op.drop_column("organization_mindbot_configs", "dingtalk_ai_card_template_id")
