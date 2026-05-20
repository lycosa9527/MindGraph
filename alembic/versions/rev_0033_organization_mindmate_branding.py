"""Add per-organization MindMate agent name and avatar on organizations.

Revision ID: 0033
Revises: 0032
Create Date: 2026-05-20

Optional ``mindmate_agent_name`` and ``mindmate_agent_avatar_url`` customize the
MindMate label and avatar shown to users in that school.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0033"
down_revision: Union[str, None] = "0032"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _org_column_names(conn) -> set[str]:
    return {c["name"] for c in sa.inspect(conn).get_columns("organizations")}


def upgrade() -> None:
    bind = op.get_bind()
    ocols = _org_column_names(bind)
    if "mindmate_agent_name" not in ocols:
        op.add_column(
            "organizations",
            sa.Column("mindmate_agent_name", sa.String(length=200), nullable=True),
        )
    if "mindmate_agent_avatar_url" not in ocols:
        op.add_column(
            "organizations",
            sa.Column("mindmate_agent_avatar_url", sa.String(length=512), nullable=True),
        )


def downgrade() -> None:
    """Additive-only migration; downgrading risks dropping columns on legacy DBs."""
