"""Org library shares for a single diagram row.

Revision ID: 0129
Revises: 0128
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0129"
down_revision: Union[str, None] = "0128"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SHARE_ACCESS = (
    "grantee_user_id = rls_current_user_id() "
    "OR shared_by_user_id = rls_current_user_id() "
    "OR EXISTS ("
    "SELECT 1 FROM diagrams d "
    "WHERE d.id = diagram_id AND d.user_id = rls_current_user_id()"
    ") "
    "OR rls_is_panel_mode() OR rls_is_system_mode()"
)


def _share_rls() -> None:
    op.execute(sa.text('ALTER TABLE "diagram_shares" ENABLE ROW LEVEL SECURITY'))
    op.execute(sa.text('ALTER TABLE "diagram_shares" FORCE ROW LEVEL SECURITY'))
    op.execute(
        sa.text(
            'CREATE POLICY "diagram_shares_all" ON "diagram_shares" '
            f"FOR ALL USING ({_SHARE_ACCESS}) WITH CHECK ({_SHARE_ACCESS})"
        )
    )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("diagram_shares"):
        return
    op.create_table(
        "diagram_shares",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("diagram_id", sa.String(length=36), nullable=False),
        sa.Column("grantee_user_id", sa.Integer(), nullable=False),
        sa.Column("shared_by_user_id", sa.Integer(), nullable=False),
        sa.Column("is_pinned", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("folder_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["diagram_id"], ["diagrams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["folder_id"], ["diagram_folders.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["grantee_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["shared_by_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("diagram_id", "grantee_user_id", name="uq_diagram_shares_diagram_grantee"),
    )
    op.create_index("ix_diagram_shares_grantee", "diagram_shares", ["grantee_user_id"])
    _share_rls()


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("diagram_shares"):
        return
    op.execute(sa.text('DROP POLICY IF EXISTS "diagram_shares_all" ON "diagram_shares"'))
    op.drop_index("ix_diagram_shares_grantee", table_name="diagram_shares")
    op.drop_table("diagram_shares")
