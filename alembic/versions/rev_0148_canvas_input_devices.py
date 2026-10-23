"""Store the canvas input mode on the browser device.

Revision ID: 0148
Revises: 0147
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from utils.db_rls.policy_builder import CANVAS_INPUT_DEVICE_EXPR

revision: str = "0148"
down_revision: Union[str, None] = "0147"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "canvas_input_devices"


def upgrade() -> None:
    bind = op.get_bind()
    if sa.inspect(bind).has_table(_TABLE):
        return
    op.create_table(
        _TABLE,
        sa.Column("device_id", sa.String(length=64), nullable=False),
        sa.Column("input_mode", sa.String(length=16), nullable=False),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("device_id"),
    )
    op.create_index("ix_canvas_input_devices_input_mode", _TABLE, ["input_mode"])
    op.execute(sa.text(f'ALTER TABLE "{_TABLE}" ENABLE ROW LEVEL SECURITY'))
    op.execute(sa.text(f'ALTER TABLE "{_TABLE}" FORCE ROW LEVEL SECURITY'))
    op.execute(
        sa.text(
            f'CREATE POLICY "{_TABLE}_tenant" ON "{_TABLE}" '
            f"FOR ALL USING ({CANVAS_INPUT_DEVICE_EXPR}) "
            f"WITH CHECK ({CANVAS_INPUT_DEVICE_EXPR})"
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table(_TABLE):
        return
    op.execute(sa.text(f'DROP POLICY IF EXISTS "{_TABLE}_tenant" ON "{_TABLE}"'))
    op.drop_index("ix_canvas_input_devices_input_mode", table_name=_TABLE)
    op.drop_table(_TABLE)
