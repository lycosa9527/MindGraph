"""School-scoped Learning Space RLS and organization_id on child tables.

Revision ID: 0125
Revises: 0124
Create Date: 2026-09-19
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from utils.db_rls.policy_builder import LEARNING_SPACE_POLICIES, upgrade_learning_space_policies

revision: str = "0125"
down_revision: Union[str, None] = "0124"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_LOOSE = "rls_is_system_mode() OR rls_is_panel_mode() OR rls_current_user_id() IS NOT NULL"

_CHILD_TABLES = (
    "learning_assignments",
    "learning_submissions",
    "learning_class_memberships",
)


def _add_organization_id(table: str) -> None:
    op.add_column(table, sa.Column("organization_id", sa.Integer(), nullable=True))
    op.create_index(f"ix_{table}_organization_id", table, ["organization_id"])
    op.create_foreign_key(
        f"fk_{table}_organization_id",
        table,
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="CASCADE",
    )


def _backfill_child_orgs() -> None:
    op.execute(
        sa.text(
            """
            UPDATE learning_assignments a
            SET organization_id = c.organization_id
            FROM learning_classes c
            WHERE a.class_id = c.id AND a.organization_id IS NULL
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE learning_submissions s
            SET organization_id = a.organization_id
            FROM learning_assignments a
            WHERE s.assignment_id = a.id AND s.organization_id IS NULL
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE learning_class_memberships m
            SET organization_id = c.organization_id
            FROM learning_classes c
            WHERE m.class_id = c.id AND m.organization_id IS NULL
            """
        )
    )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for table in _CHILD_TABLES:
        if not inspector.has_table(table):
            continue
        cols = {c["name"] for c in inspector.get_columns(table)}
        if "organization_id" not in cols:
            _add_organization_id(table)
    _backfill_child_orgs()
    inspector = sa.inspect(bind)
    for table in _CHILD_TABLES:
        if not inspector.has_table(table):
            continue
        cols = {c["name"] for c in inspector.get_columns(table)}
        if "organization_id" not in cols:
            continue
        op.execute(sa.text(f'DELETE FROM "{table}" WHERE organization_id IS NULL'))
        op.alter_column(table, "organization_id", existing_type=sa.Integer(), nullable=False)
    upgrade_learning_space_policies()


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for table, _expr in LEARNING_SPACE_POLICIES:
        if not inspector.has_table(table):
            continue
        op.execute(sa.text(f'DROP POLICY IF EXISTS "{table}_tenant" ON "{table}"'))
        op.execute(sa.text(f'CREATE POLICY "{table}_select" ON "{table}" FOR SELECT USING ({_LOOSE})'))
        op.execute(sa.text(f'CREATE POLICY "{table}_write" ON "{table}" FOR INSERT WITH CHECK ({_LOOSE})'))
        op.execute(
            sa.text(f'CREATE POLICY "{table}_update" ON "{table}" FOR UPDATE USING ({_LOOSE}) WITH CHECK ({_LOOSE})')
        )
        op.execute(sa.text(f'CREATE POLICY "{table}_delete" ON "{table}" FOR DELETE USING ({_LOOSE})'))
    for table in reversed(_CHILD_TABLES):
        if not inspector.has_table(table):
            continue
        cols = {c["name"] for c in inspector.get_columns(table)}
        if "organization_id" not in cols:
            continue
        op.drop_constraint(f"fk_{table}_organization_id", table, type_="foreignkey")
        op.drop_index(f"ix_{table}_organization_id", table_name=table)
        op.drop_column(table, "organization_id")
