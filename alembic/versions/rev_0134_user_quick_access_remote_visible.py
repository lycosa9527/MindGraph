"""Add users.quick_access_remote_visible.

Account-default quick-access remote open state. Null means closed.

Revision ID: 0134
Revises: 0133
Create Date: 2026-09-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0134"
down_revision: Union[str, None] = "0133"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _user_column_names(conn) -> set[str]:
    return {column["name"] for column in sa.inspect(conn).get_columns("users")}


def upgrade() -> None:
    bind = op.get_bind()
    ucols = _user_column_names(bind)
    if "quick_access_remote_visible" not in ucols:
        op.add_column(
            "users",
            sa.Column("quick_access_remote_visible", sa.Boolean(), nullable=True),
        )


def downgrade() -> None:
    """Additive-only; dropping may discard user preference data."""
