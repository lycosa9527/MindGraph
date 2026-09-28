"""Add organizations.mindmate_agent_alias.

Short MindMate name (小名) sent to the shared Dify chatflow as mg_agent_alias.

Revision ID: 0137
Revises: 0136
Create Date: 2026-09-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0137"
down_revision: Union[str, None] = "0136"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _org_column_names(conn) -> set[str]:
    return {column["name"] for column in sa.inspect(conn).get_columns("organizations")}


def upgrade() -> None:
    bind = op.get_bind()
    ocols = _org_column_names(bind)
    if "mindmate_agent_alias" not in ocols:
        op.add_column(
            "organizations",
            sa.Column("mindmate_agent_alias", sa.String(length=10), nullable=True),
        )


def downgrade() -> None:
    """Additive-only; dropping may discard saved agent aliases."""
