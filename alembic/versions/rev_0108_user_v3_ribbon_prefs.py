"""Add users.v3_ribbon_classic and users.v3_ribbon_tab.

Account-default V3 ribbon height and last tab (no browser storage).

Revision ID: 0108
Revises: 0107
Create Date: 2026-09-04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0108"
down_revision: Union[str, None] = "0107"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _user_column_names(conn) -> set[str]:
    return {c["name"] for c in sa.inspect(conn).get_columns("users")}


def upgrade() -> None:
    bind = op.get_bind()
    ucols = _user_column_names(bind)
    if "v3_ribbon_classic" not in ucols:
        op.add_column(
            "users",
            sa.Column("v3_ribbon_classic", sa.Boolean(), nullable=True),
        )
    if "v3_ribbon_tab" not in ucols:
        op.add_column(
            "users",
            sa.Column("v3_ribbon_tab", sa.String(length=16), nullable=True),
        )


def downgrade() -> None:
    """Additive-only; dropping may discard user preference data."""
