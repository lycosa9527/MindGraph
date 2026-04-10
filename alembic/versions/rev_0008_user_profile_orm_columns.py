"""Add User profile columns that exist on ORM but may be missing on legacy DBs.

Columns such as ``ui_version`` and ``workshop_last_seen_at`` are part of the
current ``User`` model and are created by baseline ``0001`` ``create_all`` on
fresh installs. Databases restored from older dumps may already be stamped at
``0007`` while their ``users`` table predates these fields — ``alembic upgrade``
would otherwise apply no revision. Add any missing columns idempotently.

Revision ID: 0008
Revises: 0007
Create Date: 2026-04-10
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _user_column_names(conn) -> set[str]:
    return {c["name"] for c in sa.inspect(conn).get_columns("users")}


def _org_column_names(conn) -> set[str]:
    return {c["name"] for c in sa.inspect(conn).get_columns("organizations")}


def upgrade() -> None:
    bind = op.get_bind()
    ucols = _user_column_names(bind)

    if "workshop_last_seen_at" not in ucols:
        op.add_column(
            "users",
            sa.Column("workshop_last_seen_at", sa.DateTime(), nullable=True),
        )
    if "ui_language" not in ucols:
        op.add_column(
            "users",
            sa.Column("ui_language", sa.String(length=32), nullable=True),
        )
    if "prompt_language" not in ucols:
        op.add_column(
            "users",
            sa.Column("prompt_language", sa.String(length=32), nullable=True),
        )
    if "ui_version" not in ucols:
        op.add_column(
            "users",
            sa.Column("ui_version", sa.String(length=32), nullable=True),
        )

    ocols = _org_column_names(bind)
    if "display_name" not in ocols:
        op.add_column(
            "organizations",
            sa.Column("display_name", sa.String(length=200), nullable=True),
        )


def downgrade() -> None:
    """Additive-only migration; downgrading legacy DBs risks dropping pre-existing columns."""
    pass
