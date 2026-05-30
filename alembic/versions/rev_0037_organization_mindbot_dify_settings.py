"""Per-organization shared MindBot/MindMate Dify behavior settings.

Revision ID: 0037
Revises: 0036
Create Date: 2026-05-30

Adds timeout, chain-of-thought, and AI-card streaming limits on organizations.
Backfills from the first MindBot config per school when present.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0037"
down_revision: Union[str, None] = "0036"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _org_column_names(conn) -> set[str]:
    return {c["name"] for c in sa.inspect(conn).get_columns("organizations")}


def upgrade() -> None:
    bind = op.get_bind()
    ocols = _org_column_names(bind)
    if "dify_timeout_seconds" not in ocols:
        op.add_column(
            "organizations",
            sa.Column("dify_timeout_seconds", sa.Integer(), nullable=False, server_default="300"),
        )
    if "show_chain_of_thought_oto" not in ocols:
        op.add_column(
            "organizations",
            sa.Column(
                "show_chain_of_thought_oto",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )
    if "show_chain_of_thought_internal_group" not in ocols:
        op.add_column(
            "organizations",
            sa.Column(
                "show_chain_of_thought_internal_group",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )
    if "show_chain_of_thought_cross_org_group" not in ocols:
        op.add_column(
            "organizations",
            sa.Column(
                "show_chain_of_thought_cross_org_group",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )
    if "chain_of_thought_max_chars" not in ocols:
        op.add_column(
            "organizations",
            sa.Column(
                "chain_of_thought_max_chars",
                sa.Integer(),
                nullable=False,
                server_default="4000",
            ),
        )
    if "dingtalk_ai_card_streaming_max_chars" not in ocols:
        op.add_column(
            "organizations",
            sa.Column(
                "dingtalk_ai_card_streaming_max_chars",
                sa.Integer(),
                nullable=False,
                server_default="6500",
            ),
        )

    if not sa.inspect(bind).has_table("organization_mindbot_configs"):
        return

    op.execute(
        sa.text(
            """
            UPDATE organizations AS o
            SET
                dify_timeout_seconds = sub.dify_timeout_seconds,
                show_chain_of_thought_oto = sub.show_chain_of_thought_oto,
                show_chain_of_thought_internal_group = sub.show_chain_of_thought_internal_group,
                show_chain_of_thought_cross_org_group = sub.show_chain_of_thought_cross_org_group,
                chain_of_thought_max_chars = sub.chain_of_thought_max_chars,
                dingtalk_ai_card_streaming_max_chars = sub.dingtalk_ai_card_streaming_max_chars
            FROM (
                SELECT DISTINCT ON (organization_id)
                    organization_id,
                    dify_timeout_seconds,
                    show_chain_of_thought_oto,
                    show_chain_of_thought_internal_group,
                    show_chain_of_thought_cross_org_group,
                    chain_of_thought_max_chars,
                    dingtalk_ai_card_streaming_max_chars
                FROM organization_mindbot_configs
                ORDER BY organization_id, id
            ) AS sub
            WHERE o.id = sub.organization_id
            """
        )
    )


def downgrade() -> None:
    """Additive-only migration; downgrading risks dropping columns on legacy DBs."""
