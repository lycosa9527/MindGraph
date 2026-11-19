"""Settings QR that attributes a glasses photo to the signed-in user.

Revision ID: 0171
Revises: 0170
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from utils.db_rls.policy_builder import GLASSES_SHEET_EXPR

revision: str = "0171"
down_revision: Union[str, None] = "0170"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "glasses_wearer_binds"


def upgrade() -> None:
    """Create the wearer bind table."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table(_TABLE):
        return
    op.create_table(
        _TABLE,
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("image_ref", sa.String(length=240), nullable=True),
        sa.Column("bound_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", name="uq_glasses_wearer_binds_owner"),
    )
    op.create_index("ix_glasses_wearer_binds_organization_id", _TABLE, ["organization_id"])
    op.execute(sa.text(f'ALTER TABLE "{_TABLE}" ENABLE ROW LEVEL SECURITY'))
    op.execute(sa.text(f'ALTER TABLE "{_TABLE}" FORCE ROW LEVEL SECURITY'))
    op.execute(
        sa.text(
            f'CREATE POLICY "{_TABLE}_tenant" ON "{_TABLE}" '
            f"FOR ALL USING ({GLASSES_SHEET_EXPR}) "
            f"WITH CHECK ({GLASSES_SHEET_EXPR})"
        )
    )


def downgrade() -> None:
    """Drop the wearer bind table."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(_TABLE):
        return
    op.execute(sa.text(f'DROP POLICY IF EXISTS "{_TABLE}_tenant" ON "{_TABLE}"'))
    op.drop_index("ix_glasses_wearer_binds_organization_id", table_name=_TABLE)
    op.drop_table(_TABLE)
