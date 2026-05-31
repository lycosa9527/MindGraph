"""Add invited_by_user_id on organizations for expert invite scoping.

Revision ID: 0040
Revises: 0039
Create Date: 2026-05-31

Tracks which platform user created/invited each school org (expert scope).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0040"
down_revision: Union[str, None] = "0039"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _organization_column_names(conn) -> set[str]:
    return {column["name"] for column in sa.inspect(conn).get_columns("organizations")}


def upgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("organizations"):
        return
    columns = _organization_column_names(bind)
    if "invited_by_user_id" not in columns:
        op.add_column(
            "organizations",
            sa.Column(
                "invited_by_user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )
        op.create_index(
            "ix_organizations_invited_by_user_id",
            "organizations",
            ["invited_by_user_id"],
        )


def downgrade() -> None:
    """Additive-only migration; downgrading risks dropping columns on legacy DBs."""
