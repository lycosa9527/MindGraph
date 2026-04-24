"""MindBot: DingTalk HTTP event subscription (callback URL verification) fields.

Revision ID: 0014
Revises: 0013
Create Date: 2026-04-13

Baseline ``0001`` may already create these columns (current ORM).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "organization_mindbot_configs"
_COLS = (
    "dingtalk_event_token",
    "dingtalk_event_aes_key",
    "dingtalk_event_owner_key",
)


def upgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns(_TABLE)}
    if "dingtalk_event_token" not in cols:
        op.add_column(
            _TABLE,
            sa.Column("dingtalk_event_token", sa.Text(), nullable=True),
        )
    if "dingtalk_event_aes_key" not in cols:
        op.add_column(
            _TABLE,
            sa.Column("dingtalk_event_aes_key", sa.Text(), nullable=True),
        )
    if "dingtalk_event_owner_key" not in cols:
        op.add_column(
            _TABLE,
            sa.Column("dingtalk_event_owner_key", sa.String(length=128), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns(_TABLE)}
    for name in reversed(_COLS):
        if name in cols:
            op.drop_column(_TABLE, name)
