"""RLS for user_usage_activities (user-owned, same as user_activity_log)."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0061"
down_revision: Union[str, None] = "0060"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "user_usage_activities"
_POLICY = "user_usage_activities_tenant"
_EXPR = "rls_diagram_visible(user_id)"


def upgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table(_TABLE):
        return
    op.execute(sa.text(f'ALTER TABLE "{_TABLE}" ENABLE ROW LEVEL SECURITY'))
    op.execute(sa.text(f'ALTER TABLE "{_TABLE}" FORCE ROW LEVEL SECURITY'))
    op.execute(sa.text(f'CREATE POLICY "{_POLICY}" ON "{_TABLE}" FOR ALL USING ({_EXPR}) WITH CHECK ({_EXPR})'))


def downgrade() -> None:
    op.execute(sa.text(f'DROP POLICY IF EXISTS "{_POLICY}" ON "{_TABLE}"'))
    op.execute(sa.text(f'ALTER TABLE "{_TABLE}" DISABLE ROW LEVEL SECURITY'))
