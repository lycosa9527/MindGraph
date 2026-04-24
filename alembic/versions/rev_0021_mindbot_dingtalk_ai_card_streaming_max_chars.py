"""MindBot: per-org DingTalk AI card streaming body character cap.

Revision ID: 0021
Revises: 0020
Create Date: 2026-04-16

Baseline ``0001`` may already add ``dingtalk_ai_card_streaming_max_chars`` (current ORM).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0021"
down_revision: Union[str, None] = "0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "organization_mindbot_configs"
_COL = "dingtalk_ai_card_streaming_max_chars"


def upgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns(_TABLE)}

    if _COL not in cols:
        op.add_column(
            _TABLE,
            sa.Column(
                _COL,
                sa.Integer(),
                nullable=False,
                server_default="6000",
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns(_TABLE)}
    if _COL in cols:
        op.drop_column(_TABLE, _COL)
