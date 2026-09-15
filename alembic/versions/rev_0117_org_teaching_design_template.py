"""Add per-school teaching-design Word template selection.

Revision ID: 0117
Revises: 0116
Create Date: 2026-09-15
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0117"
down_revision: Union[str, None] = "0116"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _organization_column_names(conn) -> set[str]:
    return {column["name"] for column in sa.inspect(conn).get_columns("organizations")}


def upgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("organizations"):
        return
    if "teaching_design_template_key" in _organization_column_names(bind):
        return
    op.add_column(
        "organizations",
        sa.Column("teaching_design_template_key", sa.String(length=32), nullable=True),
    )


def downgrade() -> None:
    """Additive-only migration; downgrading risks dropping columns on legacy DBs."""
