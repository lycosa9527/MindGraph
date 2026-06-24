"""RLS for mindmate_export_jobs (platform admin / job owner)."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0063"
down_revision: Union[str, None] = "0062"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "mindmate_export_jobs"
_POLICY = "mindmate_export_jobs_access"
_EXPR = "created_by_user_id = rls_current_user_id() OR rls_platform_admin_only()"


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
