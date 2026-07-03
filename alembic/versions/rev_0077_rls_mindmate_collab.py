"""RLS for mindmate_collab_sessions and mindmate_collab_messages."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from db_rls.policy_builder import (
    MINDMATE_COLLAB_TABLES,
    _create_all_policy,
    downgrade_policies_for_tables,
)

revision: str = "0077"
down_revision: Union[str, None] = "0076"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = [table for table, _, _ in MINDMATE_COLLAB_TABLES]


def upgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("mindmate_collab_sessions"):
        return
    for table, using_expr, check_expr in MINDMATE_COLLAB_TABLES:
        op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY'))
        _create_all_policy(table, f"{table}_tenant", using_expr, check_expr)


def downgrade() -> None:
    downgrade_policies_for_tables(_TABLES)
