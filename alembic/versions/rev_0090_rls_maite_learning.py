"""RLS for Mate Learning user-scoped tables.

Revision ID: 0090
Revises: 0089
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0090"
down_revision: Union[str, None] = "0089"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_EXPR = "rls_diagram_visible(user_id)"

_TABLES = (
    "maite_problems",
    "maite_inquiry_sessions",
    "maite_graph_node_progress",
    "maite_prompt_runs",
)


def _apply_rls(table: str) -> None:
    policy = f"{table}_tenant"
    op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
    op.execute(sa.text(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY'))
    op.execute(sa.text(f'CREATE POLICY "{policy}" ON "{table}" FOR ALL USING ({_EXPR}) WITH CHECK ({_EXPR})'))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for table in _TABLES:
        if inspector.has_table(table):
            _apply_rls(table)


def downgrade() -> None:
    for table in _TABLES:
        op.execute(sa.text(f'DROP POLICY IF EXISTS "{table}_tenant" ON "{table}"'))
        op.execute(sa.text(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY'))
