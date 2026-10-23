"""People who joined a MindMate seminar keep it in their history.

Revision ID: 0146
Revises: 0145
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from utils.db_rls.policy_builder import (
    MINDMATE_COLLAB_MEMBER_CHECK,
    MINDMATE_COLLAB_MEMBER_EXPR,
    _create_all_policy,
)

revision: str = "0146"
down_revision: Union[str, None] = "0145"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "mindmate_collab_members"


def upgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table(_TABLE):
        op.create_table(
            _TABLE,
            sa.Column("session_id", sa.String(length=36), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(
                ["session_id"],
                ["mindmate_collab_sessions.id"],
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("session_id", "user_id"),
        )
        op.create_index("ix_mindmate_collab_members_user", _TABLE, ["user_id"])
        op.execute(sa.text(f'ALTER TABLE "{_TABLE}" ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'ALTER TABLE "{_TABLE}" FORCE ROW LEVEL SECURITY'))
        _create_all_policy(
            _TABLE,
            f"{_TABLE}_tenant",
            MINDMATE_COLLAB_MEMBER_EXPR,
            MINDMATE_COLLAB_MEMBER_CHECK,
        )
    # The migration role is subject to FORCE RLS. System mode lets the backfill
    # read every seminar row and insert members that are not the current user.
    op.execute(sa.text("SELECT set_config('app.rls_mode', 'system', true)"))
    op.execute(
        sa.text(
            "INSERT INTO mindmate_collab_members (session_id, user_id, joined_at) "
            "SELECT id, owner_user_id, started_at FROM mindmate_collab_sessions "
            "ON CONFLICT (session_id, user_id) DO NOTHING"
        )
    )
    op.execute(
        sa.text(
            "INSERT INTO mindmate_collab_members (session_id, user_id, joined_at) "
            "SELECT session_id, sender_user_id, MIN(created_at) "
            "FROM mindmate_collab_messages "
            "WHERE sender_user_id IS NOT NULL "
            "GROUP BY session_id, sender_user_id "
            "ON CONFLICT (session_id, user_id) DO NOTHING"
        )
    )
    op.execute(
        sa.text(
            "INSERT INTO mindmate_collab_members (session_id, user_id, joined_at) "
            "SELECT session_id, user_id, read_at FROM mindmate_collab_read_cursors "
            "ON CONFLICT (session_id, user_id) DO NOTHING"
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    if sa.inspect(bind).has_table(_TABLE):
        op.drop_table(_TABLE)
