"""RLS for Maite session child tables and task references.

Revision ID: 0091
Revises: 0090
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from db_rls.policy_builder import (
    MAITE_CHILD_TABLES,
    MAITE_TASK_REFERENCE_EXPR,
    _create_all_policy,
    _drop_policy,
    downgrade_policies_for_tables,
)

revision: str = "0091"
down_revision: Union[str, None] = "0090"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CHILD_TABLES = [table for table, _ in MAITE_CHILD_TABLES]
_ALL_TABLES = [*_CHILD_TABLES, "maite_task_references"]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for table, expr in MAITE_CHILD_TABLES:
        if not inspector.has_table(table):
            continue
        op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY'))
        policy = f"{table}_tenant"
        _drop_policy(table, policy)
        _create_all_policy(table, policy, expr)
    if inspector.has_table("maite_task_references"):
        op.execute(sa.text('ALTER TABLE "maite_task_references" ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text('ALTER TABLE "maite_task_references" FORCE ROW LEVEL SECURITY'))
        _drop_policy("maite_task_references", "maite_task_references_tenant")
        _create_all_policy(
            "maite_task_references",
            "maite_task_references_tenant",
            MAITE_TASK_REFERENCE_EXPR,
        )


def downgrade() -> None:
    downgrade_policies_for_tables(_ALL_TABLES)
