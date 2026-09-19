"""Add users.classroom_remote_visible.

Account-default new-canvas classroom remote open state.

Revision ID: 0120
Revises: 0119
Create Date: 2026-09-19
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0120"
down_revision: Union[str, None] = "0119"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _user_column_names(conn) -> set[str]:
    return {column["name"] for column in sa.inspect(conn).get_columns("users")}


def upgrade() -> None:
    bind = op.get_bind()
    ucols = _user_column_names(bind)
    if "classroom_remote_visible" not in ucols:
        op.add_column(
            "users",
            sa.Column("classroom_remote_visible", sa.Boolean(), nullable=True),
        )


def downgrade() -> None:
    """Additive-only; dropping may discard user preference data."""
