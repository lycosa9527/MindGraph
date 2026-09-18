"""Add users.bilingual_ui_enabled and users.presenter_ui_locale.

Revision ID: 0119
Revises: 0118
Create Date: 2026-09-18
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0119"
down_revision: Union[str, None] = "0118"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _user_column_names(conn) -> set[str]:
    return {column["name"] for column in sa.inspect(conn).get_columns("users")}


def upgrade() -> None:
    bind = op.get_bind()
    ucols = _user_column_names(bind)
    if "bilingual_ui_enabled" not in ucols:
        op.add_column(
            "users",
            sa.Column(
                "bilingual_ui_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )
    if "presenter_ui_locale" not in ucols:
        op.add_column(
            "users",
            sa.Column("presenter_ui_locale", sa.String(length=32), nullable=True),
        )


def downgrade() -> None:
    """Additive-only; dropping may discard user preference data."""
