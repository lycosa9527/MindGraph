"""Read cursors for MindMate seminar lines.

Revision ID: 0140
Revises: 0139
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from utils.db_rls.policy_builder import _create_all_policy

# Revision 0145 installs rls_user_bound_to_org and then replaces this policy.
# Keep the expression free of that function so upgrades can pass 0140 first.
_READ_EXPR = (
    "EXISTS (SELECT 1 FROM mindmate_collab_sessions s WHERE s.id = session_id AND ("
    "s.owner_user_id = rls_current_user_id() "
    "OR (s.visibility = 'network' AND rls_community_read_allowed()) "
    "OR (s.organization_id IS NOT NULL AND rls_org_visible(s.organization_id)) "
    "OR rls_platform_admin_only() "
    "OR rls_is_system_mode()"
    "))"
)
_READ_CHECK = _READ_EXPR + " AND (user_id = rls_current_user_id() OR rls_is_system_mode())"

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
    _create_all_policy(_TABLE, f"{_TABLE}_tenant", _READ_EXPR, _READ_CHECK)


def downgrade() -> None:
    bind = op.get_bind()
    if sa.inspect(bind).has_table(_TABLE):
        op.drop_table(_TABLE)
