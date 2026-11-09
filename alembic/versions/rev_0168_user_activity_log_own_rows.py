"""Teachers read only their own user_activity_log rows.

The table used the diagram rule, which also shows schoolmates' rows. Admin
panels and system jobs keep reading across users.

Revision ID: 0168
Revises: 0167
"""

from typing import Sequence, Union

from utils.db_rls.policy_builder import (
    USER_ACTIVITY_LOG_EXPR,
    USER_ACTIVITY_LOG_TABLE,
    USER_OWNED_EXPR,
    _create_all_policy,
    _enable_force,
)

revision: str = "0168"
down_revision: Union[str, None] = "0167"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_POLICY = f"{USER_ACTIVITY_LOG_TABLE}_tenant"


def upgrade() -> None:
    """Replace the school-visible policy with own-rows-or-admin."""
    _enable_force(USER_ACTIVITY_LOG_TABLE)
    _create_all_policy(USER_ACTIVITY_LOG_TABLE, _POLICY, USER_ACTIVITY_LOG_EXPR)


def downgrade() -> None:
    """Restore the diagram rule."""
    _create_all_policy(USER_ACTIVITY_LOG_TABLE, _POLICY, USER_OWNED_EXPR)
