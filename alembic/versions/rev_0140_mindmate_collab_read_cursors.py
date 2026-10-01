"""Read cursors for MindMate seminar lines.

Revision ID: 0140
Revises: 0139
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from utils.db_rls.policy_builder import (
    MINDMATE_COLLAB_READ_CHECK,
    MINDMATE_COLLAB_READ_EXPR,
    _create_all_policy,
)

revision: str = "0140"
down_revision: Union[str, None] = "0139"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "mindmate_collab_read_cursors"


def upgrade() -> None:
    bind = op.get_bind()
    if sa.inspect(bind).has_table(_TABLE):
        return
    op.create_table(
        _TABLE,
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("last_read_message_id", sa.Integer(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["mindmate_collab_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("session_id", "user_id"),
    )
    op.execute(sa.text(f'ALTER TABLE "{_TABLE}" ENABLE ROW LEVEL SECURITY'))
    op.execute(sa.text(f'ALTER TABLE "{_TABLE}" FORCE ROW LEVEL SECURITY'))
    _create_all_policy(_TABLE, f"{_TABLE}_tenant", MINDMATE_COLLAB_READ_EXPR, MINDMATE_COLLAB_READ_CHECK)


def downgrade() -> None:
    bind = op.get_bind()
    if sa.inspect(bind).has_table(_TABLE):
        op.drop_table(_TABLE)
