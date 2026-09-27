"""Add users.quick_access_prompt_overrides.

Custom text for the six quick-access inspiration prompts. Null means presets.

Revision ID: 0135
Revises: 0134
Create Date: 2026-09-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0135"
down_revision: Union[str, None] = "0134"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _user_column_names(conn) -> set[str]:
    return {column["name"] for column in sa.inspect(conn).get_columns("users")}


def upgrade() -> None:
    bind = op.get_bind()
    ucols = _user_column_names(bind)
    if "quick_access_prompt_overrides" not in ucols:
        op.add_column(
            "users",
            sa.Column("quick_access_prompt_overrides", JSONB, nullable=True),
        )


def downgrade() -> None:
    """Additive-only; dropping may discard user preference data."""
