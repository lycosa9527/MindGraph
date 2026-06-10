"""Add extra member seats on organizations.

Revision ID: 0054
Revises: 0053
Create Date: 2026-06-08

Adds extra_member_seats (bonus seats above tier base member cap).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0054"
down_revision: Union[str, None] = "0053"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _organization_column_names(conn) -> set[str]:
    return {column["name"] for column in sa.inspect(conn).get_columns("organizations")}


def upgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("organizations"):
        return
    columns = _organization_column_names(bind)
    if "extra_member_seats" not in columns:
        op.add_column(
            "organizations",
            sa.Column(
                "extra_member_seats",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
        )


def downgrade() -> None:
    """Additive-only migration; downgrading risks dropping columns on legacy DBs."""
