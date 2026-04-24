"""MindBot: optional DingTalk AI card template for OpenAPI streaming replies.

Revision ID: 0018
Revises: 0017
Create Date: 2026-04-14

Baseline ``0001`` may already add these columns (current ORM).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: Union[str, None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "organization_mindbot_configs"


def upgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns(_TABLE)}

    if "dingtalk_ai_card_template_id" not in cols:
        op.add_column(
            _TABLE,
            sa.Column("dingtalk_ai_card_template_id", sa.String(length=128), nullable=True),
        )
    if "dingtalk_ai_card_param_key" not in cols:
        op.add_column(
            _TABLE,
            sa.Column("dingtalk_ai_card_param_key", sa.String(length=128), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns(_TABLE)}
    if "dingtalk_ai_card_param_key" in cols:
        op.drop_column(_TABLE, "dingtalk_ai_card_param_key")
    if "dingtalk_ai_card_template_id" in cols:
        op.drop_column(_TABLE, "dingtalk_ai_card_template_id")
