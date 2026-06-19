"""Add dingtalk_staff_links for MindBot account binding.

Revision ID: 0055
Revises: 0054
Create Date: 2026-06-18
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0055"
down_revision: Union[str, None] = "0054"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if sa.inspect(bind).has_table("dingtalk_staff_links"):
        return
    op.create_table(
        "dingtalk_staff_links",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("dingtalk_staff_id", sa.String(length=128), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("linked_via", sa.String(length=32), nullable=False, server_default="qr_bind"),
        sa.Column("linked_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "dingtalk_staff_id",
            name="uq_dingtalk_staff_links_org_staff",
        ),
    )
    op.create_index(
        "ix_dingtalk_staff_links_org_id",
        "dingtalk_staff_links",
        ["organization_id"],
    )
    op.create_index(
        "ix_dingtalk_staff_links_user_id",
        "dingtalk_staff_links",
        ["user_id"],
    )
    op.create_index(
        "ix_dingtalk_staff_links_user_org",
        "dingtalk_staff_links",
        ["user_id", "organization_id"],
    )


def downgrade() -> None:
    """Additive-only migration; downgrading risks dropping columns on legacy DBs."""
