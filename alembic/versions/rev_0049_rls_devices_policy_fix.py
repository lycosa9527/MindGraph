"""Fix devices RLS policy — column is student_id, not user_id.

Revision ID: 0049
Revises: 0048
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from alembic.rls_policy_builder import DEVICE_EXPR, _drop_policy, _create_all_policy

revision: str = "0049"
down_revision: Union[str, None] = "0048"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("devices"):
        return
    _drop_policy("devices", "devices_tenant")
    _create_all_policy("devices", "devices_tenant", DEVICE_EXPR)


def downgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("devices"):
        return
    _drop_policy("devices", "devices_tenant")
    _create_all_policy("devices", "devices_tenant", "rls_diagram_visible(user_id)")
