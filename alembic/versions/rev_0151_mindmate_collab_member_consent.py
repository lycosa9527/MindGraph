"""Pending consent for cross-school seminar members.

Revision ID: 0151
Revises: 0150
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0151"
down_revision: Union[str, None] = "0150"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "mindmate_collab_members"


def upgrade() -> None:
    bind = op.get_bind()
    cols = {col["name"] for col in sa.inspect(bind).get_columns(_TABLE)}
    if "accepted" not in cols:
        op.add_column(
            _TABLE,
            sa.Column("accepted", sa.Boolean(), nullable=False, server_default=sa.true()),
        )


def downgrade() -> None:
    bind = op.get_bind()
    cols = {col["name"] for col in sa.inspect(bind).get_columns(_TABLE)}
    if "accepted" in cols:
        op.drop_column(_TABLE, "accepted")
