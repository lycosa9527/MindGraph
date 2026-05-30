"""Persist per-bot MindBot Dify source (school MindMate vs custom).

Revision ID: 0038
Revises: 0037
Create Date: 2026-05-30

Adds use_org_dify_settings on organization_mindbot_configs (default true).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0038"
down_revision: Union[str, None] = "0037"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _mindbot_column_names(conn) -> set[str]:
    return {c["name"] for c in sa.inspect(conn).get_columns("organization_mindbot_configs")}


def upgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("organization_mindbot_configs"):
        return
    cols = _mindbot_column_names(bind)
    if "use_org_dify_settings" not in cols:
        op.add_column(
            "organization_mindbot_configs",
            sa.Column(
                "use_org_dify_settings",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            ),
        )


def downgrade() -> None:
    """Additive-only migration; downgrading risks dropping columns on legacy DBs."""
