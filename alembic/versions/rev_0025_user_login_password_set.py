"""Add users.login_password_set for quick-registration vs change-password UI.

Quick registration creates users with a server-only password hash; the flag
is False until the user sets a known password. Defaults to true for all
existing rows.

Revision ID: 0025
Revises: 0024
Create Date: 2026-04-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0025"
down_revision: Union[str, None] = "0024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _user_column_names(conn) -> set[str]:
    return {c["name"] for c in sa.inspect(conn).get_columns("users")}


def upgrade() -> None:
    bind = op.get_bind()
    ucols = _user_column_names(bind)
    if "login_password_set" not in ucols:
        op.add_column(
            "users",
            sa.Column(
                "login_password_set",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("1"),
            ),
        )


def downgrade() -> None:
    """Additive-only; dropping boolean on users risks losing semantics."""
    pass
