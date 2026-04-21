"""MindBot: raise DingTalk AI card streaming max chars default to 6500.

Revision ID: 0024
Revises: 0023
Create Date: 2026-04-21

Only changes the column server default for new rows; existing values are unchanged.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0024"
down_revision: Union[str, None] = "0023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "organization_mindbot_configs",
        "dingtalk_ai_card_streaming_max_chars",
        server_default="6500",
        existing_type=sa.Integer(),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "organization_mindbot_configs",
        "dingtalk_ai_card_streaming_max_chars",
        server_default="6000",
        existing_type=sa.Integer(),
        existing_nullable=False,
    )
