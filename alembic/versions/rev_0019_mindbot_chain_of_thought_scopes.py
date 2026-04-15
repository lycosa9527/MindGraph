"""MindBot: per-chat chain-of-thought (1:1, internal group, cross-org group).

Revision ID: 0019
Revises: 0018
Create Date: 2026-04-15
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0019"
down_revision: Union[str, None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "organization_mindbot_configs",
        sa.Column(
            "show_chain_of_thought_oto",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "organization_mindbot_configs",
        sa.Column(
            "show_chain_of_thought_internal_group",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "organization_mindbot_configs",
        sa.Column(
            "show_chain_of_thought_cross_org_group",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE organization_mindbot_configs SET "
            "show_chain_of_thought_oto = show_chain_of_thought, "
            "show_chain_of_thought_internal_group = show_chain_of_thought, "
            "show_chain_of_thought_cross_org_group = show_chain_of_thought"
        )
    )
    op.drop_column("organization_mindbot_configs", "show_chain_of_thought")


def downgrade() -> None:
    op.add_column(
        "organization_mindbot_configs",
        sa.Column(
            "show_chain_of_thought",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE organization_mindbot_configs SET show_chain_of_thought = "
            "(show_chain_of_thought_oto OR show_chain_of_thought_internal_group OR "
            "show_chain_of_thought_cross_org_group)"
        )
    )
    op.drop_column("organization_mindbot_configs", "show_chain_of_thought_cross_org_group")
    op.drop_column("organization_mindbot_configs", "show_chain_of_thought_internal_group")
    op.drop_column("organization_mindbot_configs", "show_chain_of_thought_oto")
