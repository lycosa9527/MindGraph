"""Add school subscription tier on organizations.

Revision ID: 0039
Revises: 0038
Create Date: 2026-05-30

Adds school_tier (lite | standard | professional) with default standard.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0039"
down_revision: Union[str, None] = "0038"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _organization_column_names(conn) -> set[str]:
    return {column["name"] for column in sa.inspect(conn).get_columns("organizations")}


def upgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("organizations"):
        return
    columns = _organization_column_names(bind)
    if "school_tier" not in columns:
        op.add_column(
            "organizations",
            sa.Column(
                "school_tier",
                sa.String(length=32),
                nullable=False,
                server_default="standard",
            ),
        )


def downgrade() -> None:
    """Additive-only migration; downgrading risks dropping columns on legacy DBs."""
