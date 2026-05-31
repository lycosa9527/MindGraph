"""Default organization school tier to trial (体验版).

Revision ID: 0041
Revises: 0040
Create Date: 2026-05-31

Adds trial tier as default for new orgs; migrates legacy implicit standard rows to trial.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0041"
down_revision: Union[str, None] = "0040"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("organizations"):
        return
    columns = {column["name"] for column in sa.inspect(bind).get_columns("organizations")}
    if "school_tier" not in columns:
        return
    op.execute(
        sa.text(
            "UPDATE organizations SET school_tier = 'trial' WHERE school_tier = 'standard'"
        )
    )
    op.alter_column(
        "organizations",
        "school_tier",
        server_default="trial",
        existing_type=sa.String(length=32),
        existing_nullable=False,
    )


def downgrade() -> None:
    """Additive-only migration; downgrading risks dropping columns on legacy DBs."""
