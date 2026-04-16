"""MindBot: per-org DingTalk AI card streaming body character cap.

Revision ID: 0021
Revises: 0020
Create Date: 2026-04-16
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0021"
down_revision: Union[str, None] = "0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "organization_mindbot_configs",
        sa.Column(
            "dingtalk_ai_card_streaming_max_chars",
            sa.Integer(),
            nullable=False,
            server_default="6000",
        ),
    )


def downgrade() -> None:
    op.drop_column("organization_mindbot_configs", "dingtalk_ai_card_streaming_max_chars")
