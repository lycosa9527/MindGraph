"""Store the mobile or desktop shell on the browser device.

Revision ID: 0158
Revises: 0157
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from utils.db_rls.policy_builder import CLIENT_SHELL_DEVICE_EXPR

revision: str = "0158"
down_revision: Union[str, None] = "0157"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "client_shell_devices"
_CHECK = "ck_client_shell_devices_shell"
_SHELL_SQL = "shell IN ('mobile', 'desktop')"


def _ensure_shell_check() -> None:
    """Add the shell check when this revision was applied before the constraint existed."""
    bind = op.get_bind()
    names = {item["name"] for item in sa.inspect(bind).get_check_constraints(_TABLE)}
    if _CHECK in names:
        return
    op.create_check_constraint(_CHECK, _TABLE, _SHELL_SQL)


def upgrade() -> None:
    bind = op.get_bind()
    if sa.inspect(bind).has_table(_TABLE):
        _ensure_shell_check()
        return
    op.create_table(
        _TABLE,
        sa.Column("device_id", sa.String(length=64), nullable=False),
        sa.Column("shell", sa.String(length=16), nullable=False),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("device_id"),
        sa.CheckConstraint(_SHELL_SQL, name=_CHECK),
    )
    op.execute(sa.text(f'ALTER TABLE "{_TABLE}" ENABLE ROW LEVEL SECURITY'))
    op.execute(sa.text(f'ALTER TABLE "{_TABLE}" FORCE ROW LEVEL SECURITY'))
    op.execute(
        sa.text(
            f'CREATE POLICY "{_TABLE}_tenant" ON "{_TABLE}" '
            f"FOR ALL USING ({CLIENT_SHELL_DEVICE_EXPR}) "
            f"WITH CHECK ({CLIENT_SHELL_DEVICE_EXPR})"
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table(_TABLE):
        return
    op.execute(sa.text(f'DROP POLICY IF EXISTS "{_TABLE}_tenant" ON "{_TABLE}"'))
    op.drop_table(_TABLE)
