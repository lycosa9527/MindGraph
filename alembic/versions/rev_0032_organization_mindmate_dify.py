"""Add per-organization MindMate Dify credentials on organizations.

Revision ID: 0032
Revises: 0031
Create Date: 2026-05-20

Optional ``dify_api_base_url`` and ``dify_api_key`` for school-specific MindMate
apps. When both are set, MindMate routes use them; otherwise global env vars apply.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0032"
down_revision: Union[str, None] = "0031"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _org_column_names(conn) -> set[str]:
    return {c["name"] for c in sa.inspect(conn).get_columns("organizations")}


def upgrade() -> None:
    bind = op.get_bind()
    ocols = _org_column_names(bind)
    if "dify_api_base_url" not in ocols:
        op.add_column(
            "organizations",
            sa.Column("dify_api_base_url", sa.String(length=512), nullable=True),
        )
    if "dify_api_key" not in ocols:
        op.add_column(
            "organizations",
            sa.Column("dify_api_key", sa.Text(), nullable=True),
        )


def downgrade() -> None:
    """Additive-only migration; downgrading risks dropping columns on legacy DBs."""
