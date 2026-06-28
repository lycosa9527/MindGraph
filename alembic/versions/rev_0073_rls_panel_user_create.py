"""RLS: allow panel school managers to INSERT users (organization_id set, id not yet assigned).

Revision ID: 0073
Revises: 0072
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from db_rls.policy_builder import USERS_EXPR, _create_all_policy, _drop_policy

revision: str = "0073"
down_revision: Union[str, None] = "0072"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_USERS_EXPR_BEFORE = "rls_user_visible(id)"


def upgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("users"):
        return
    _drop_policy("users", "users_tenant")
    _create_all_policy("users", "users_tenant", USERS_EXPR)


def downgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("users"):
        return
    _drop_policy("users", "users_tenant")
    _create_all_policy("users", "users_tenant", _USERS_EXPR_BEFORE)
