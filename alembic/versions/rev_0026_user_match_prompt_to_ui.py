"""Add users.match_prompt_to_ui — sync UI vs AI prompt language preference.

Persisted with ui_language / prompt_language so returning users keep the same behavior.

Revision ID: 0026
Revises: 0025
Create Date: 2026-04-29
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0026"
down_revision: Union[str, None] = "0025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _user_column_names(conn) -> set[str]:
    return {c["name"] for c in sa.inspect(conn).get_columns("users")}


def upgrade() -> None:
    bind = op.get_bind()
    ucols = _user_column_names(bind)
    if "match_prompt_to_ui" not in ucols:
        op.add_column(
            "users",
            sa.Column(
                "match_prompt_to_ui",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            ),
        )


def downgrade() -> None:
    """Additive-only; dropping boolean on users risks losing semantics."""
