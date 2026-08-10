"""Add users.education_stage — AI generate audience preference.

Persisted with other user prefs so canvas auto-complete can inject 学段 context.

Revision ID: 0101
Revises: 0100
Create Date: 2026-08-08
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0101"
down_revision: Union[str, None] = "0100"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _user_column_names(conn) -> set[str]:
    return {c["name"] for c in sa.inspect(conn).get_columns("users")}


def upgrade() -> None:
    bind = op.get_bind()
    ucols = _user_column_names(bind)
    if "education_stage" not in ucols:
        op.add_column(
            "users",
            sa.Column("education_stage", sa.String(length=32), nullable=True),
        )


def downgrade() -> None:
    """Additive-only; dropping may discard user preference data."""
