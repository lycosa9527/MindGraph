"""MindBot: optional Dify app inputs JSON per organization.

Revision ID: 0013
Revises: 0012
Create Date: 2026-04-13

Baseline ``0001`` ``create_all`` may already add ``dify_inputs_json`` (current ORM).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "organization_mindbot_configs"
_COL = "dify_inputs_json"


def upgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns(_TABLE)}
    if _COL not in cols:
        op.add_column(
            _TABLE,
            sa.Column(_COL, sa.Text(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns(_TABLE)}
    if _COL in cols:
        op.drop_column(_TABLE, _COL)
