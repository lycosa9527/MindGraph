"""Add per-school custom native LLM endpoint settings.

Revision ID: 0118
Revises: 0117
Create Date: 2026-09-18
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0118"
down_revision: Union[str, None] = "0117"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _organization_column_names(conn) -> set[str]:
    return {column["name"] for column in sa.inspect(conn).get_columns("organizations")}


def upgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("organizations"):
        return
    columns = _organization_column_names(bind)
    if "custom_llm_api_type" not in columns:
        op.add_column(
            "organizations",
            sa.Column(
                "custom_llm_api_type",
                sa.String(length=32),
                nullable=False,
                server_default="dashscope_volcengine",
            ),
        )
    if "custom_llm_base_url" not in columns:
        op.add_column(
            "organizations",
            sa.Column("custom_llm_base_url", sa.String(length=512), nullable=True),
        )
    if "custom_llm_api_key" not in columns:
        op.add_column(
            "organizations",
            sa.Column("custom_llm_api_key", sa.Text(), nullable=True),
        )
    if "custom_llm_model" not in columns:
        op.add_column(
            "organizations",
            sa.Column("custom_llm_model", sa.String(length=128), nullable=True),
        )


def downgrade() -> None:
    """Additive-only migration; downgrading risks dropping columns on legacy DBs."""
