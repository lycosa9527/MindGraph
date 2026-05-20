"""Shorten organizations.mindmate_agent_name to 10 characters.

Revision ID: 0034
Revises: 0033
Create Date: 2026-05-20

Truncates existing values longer than 10 characters before narrowing the column.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0034"
down_revision: Union[str, None] = "0033"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_AGENT_NAME_MAX = 10


def _org_column_names(conn) -> set[str]:
    return {c["name"] for c in sa.inspect(conn).get_columns("organizations")}


def upgrade() -> None:
    bind = op.get_bind()
    ocols = _org_column_names(bind)
    if "mindmate_agent_name" not in ocols:
        return

    op.execute(
        sa.text(
            "UPDATE organizations "
            "SET mindmate_agent_name = SUBSTRING(mindmate_agent_name FROM 1 FOR :max_len) "
            "WHERE mindmate_agent_name IS NOT NULL "
            "AND char_length(mindmate_agent_name) > :max_len"
        ).bindparams(max_len=_AGENT_NAME_MAX)
    )
    op.alter_column(
        "organizations",
        "mindmate_agent_name",
        existing_type=sa.String(length=200),
        type_=sa.String(length=_AGENT_NAME_MAX),
        existing_nullable=True,
    )


def downgrade() -> None:
    bind = op.get_bind()
    ocols = _org_column_names(bind)
    if "mindmate_agent_name" not in ocols:
        return

    op.alter_column(
        "organizations",
        "mindmate_agent_name",
        existing_type=sa.String(length=_AGENT_NAME_MAX),
        type_=sa.String(length=200),
        existing_nullable=True,
    )
