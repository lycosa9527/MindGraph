"""Add users.ai_content_level — mind-map 专业程度 preference.

Persisted with other user prefs so the new-canvas picker survives login/devices.

Revision ID: 0102
Revises: 0101
Create Date: 2026-08-16
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0102"
down_revision: Union[str, None] = "0101"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _user_column_names(conn) -> set[str]:
    return {c["name"] for c in sa.inspect(conn).get_columns("users")}


def upgrade() -> None:
    bind = op.get_bind()
    ucols = _user_column_names(bind)
    if "ai_content_level" not in ucols:
        op.add_column(
            "users",
            sa.Column("ai_content_level", sa.String(length=32), nullable=True),
        )


def downgrade() -> None:
    """Additive-only; dropping may discard user preference data."""
