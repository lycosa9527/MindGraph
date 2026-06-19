"""Add dual Dify server (Server 1 / Server 2) failover columns on organizations.

Revision ID: 0058
Revises: 0057
Create Date: 2026-06-19

Adds a second Dify endpoint (dify_api_base_url_2/dify_api_key_2), the active
server selector (dify_active_server, 1 or 2) and the failover toggle
(dify_failover_enabled). Server 1 reuses the existing dify_api_* columns.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0058"
down_revision: Union[str, None] = "0057"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _organization_column_names(conn) -> set[str]:
    return {column["name"] for column in sa.inspect(conn).get_columns("organizations")}


def upgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("organizations"):
        return
    columns = _organization_column_names(bind)
    if "dify_api_base_url_2" not in columns:
        op.add_column(
            "organizations",
            sa.Column("dify_api_base_url_2", sa.String(length=512), nullable=True),
        )
    if "dify_api_key_2" not in columns:
        op.add_column(
            "organizations",
            sa.Column("dify_api_key_2", sa.Text(), nullable=True),
        )
    if "dify_active_server" not in columns:
        op.add_column(
            "organizations",
            sa.Column(
                "dify_active_server",
                sa.Integer(),
                nullable=False,
                server_default="1",
            ),
        )
    if "dify_failover_enabled" not in columns:
        op.add_column(
            "organizations",
            sa.Column(
                "dify_failover_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            ),
        )


def downgrade() -> None:
    """Additive-only migration; downgrading risks dropping columns on legacy DBs."""
