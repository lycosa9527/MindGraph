"""MindBot: optional chain-of-thought display for DingTalk replies.

Revision ID: 0017
Revises: 0016
Create Date: 2026-04-14
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: Union[str, None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "organization_mindbot_configs",
        sa.Column(
            "show_chain_of_thought",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "organization_mindbot_configs",
        sa.Column(
            "chain_of_thought_max_chars",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("4000"),
        ),
    )


def downgrade() -> None:
    op.drop_column("organization_mindbot_configs", "chain_of_thought_max_chars")
    op.drop_column("organization_mindbot_configs", "show_chain_of_thought")
