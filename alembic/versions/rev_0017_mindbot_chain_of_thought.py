"""MindBot: optional chain-of-thought display for DingTalk replies.

Revision ID: 0017
Revises: 0016
Create Date: 2026-04-14

Baseline ``0001`` may already include these columns (current ORM).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: Union[str, None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "organization_mindbot_configs"


def upgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns(_TABLE)}

    if "show_chain_of_thought" not in cols:
        op.add_column(
            _TABLE,
            sa.Column(
                "show_chain_of_thought",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )
    if "chain_of_thought_max_chars" not in cols:
        op.add_column(
            _TABLE,
            sa.Column(
                "chain_of_thought_max_chars",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("4000"),
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns(_TABLE)}
    if "chain_of_thought_max_chars" in cols:
        op.drop_column(_TABLE, "chain_of_thought_max_chars")
    if "show_chain_of_thought" in cols:
        op.drop_column(_TABLE, "show_chain_of_thought")
