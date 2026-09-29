"""Per-user library demo playlists, notes, and type styles.

Revision ID: 0138
Revises: 0137
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0138"
down_revision: Union[str, None] = "0137"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "user_library_demos"
_ACCESS = "user_id = rls_current_user_id() OR rls_is_panel_mode() OR rls_is_system_mode()"


def _enable_rls() -> None:
    op.execute(sa.text(f'ALTER TABLE "{_TABLE}" ENABLE ROW LEVEL SECURITY'))
    op.execute(sa.text(f'ALTER TABLE "{_TABLE}" FORCE ROW LEVEL SECURITY'))
    op.execute(sa.text(f'CREATE POLICY "{_TABLE}_select" ON "{_TABLE}" FOR SELECT USING ({_ACCESS})'))
    op.execute(sa.text(f'CREATE POLICY "{_TABLE}_write" ON "{_TABLE}" FOR INSERT WITH CHECK ({_ACCESS})'))
    op.execute(
        sa.text(f'CREATE POLICY "{_TABLE}_update" ON "{_TABLE}" FOR UPDATE USING ({_ACCESS}) WITH CHECK ({_ACCESS})')
    )
    op.execute(sa.text(f'CREATE POLICY "{_TABLE}_delete" ON "{_TABLE}" FOR DELETE USING ({_ACCESS})'))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table(_TABLE):
        return
    op.create_table(
        _TABLE,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_user_library_demos_user_id"),
    )
    _enable_rls()


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(_TABLE):
        return
    op.execute(sa.text(f'DROP POLICY IF EXISTS "{_TABLE}_select" ON "{_TABLE}"'))
    op.execute(sa.text(f'DROP POLICY IF EXISTS "{_TABLE}_write" ON "{_TABLE}"'))
    op.execute(sa.text(f'DROP POLICY IF EXISTS "{_TABLE}_update" ON "{_TABLE}"'))
    op.execute(sa.text(f'DROP POLICY IF EXISTS "{_TABLE}_delete" ON "{_TABLE}"'))
    op.drop_table(_TABLE)
