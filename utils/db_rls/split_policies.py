"""Tables whose read rule is wider than their write rule.

A single ``FOR ALL`` policy applies the read expression to INSERT, UPDATE and
DELETE as well. These tables get four policies instead, so a session that may
read a row cannot also rewrite or delete it.

Installed by the catalog reapply (rev_0167 onward). Diagram reads use workshop
columns that the original 0044 catalog predates.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# Recipients read a shared diagram and workshop participants read the host's
# diagram. Both save through an owner session or system mode, so writes stay
# with the owner.
DIAGRAMS_TABLE = "diagrams"
DIAGRAM_READ_EXPR = (
    "rls_diagram_visible(user_id) "
    "OR rls_diagram_shared_with_current_user(id) "
    "OR rls_diagram_workshop_visible(user_id, workshop_code, workshop_visibility)"
)
DIAGRAM_WRITE_EXPR = "rls_diagram_visible(user_id)"

# Content-hash cache shared by every school. Writers switch to system mode.
EMBEDDINGS_TABLE = "embeddings"
EMBEDDINGS_READ_EXPR = "rls_community_read_allowed()"
EMBEDDINGS_WRITE_EXPR = "rls_is_system_mode()"

# Classification thresholds. Login recomputes a teacher's own stats with them.
TEACHER_USAGE_CONFIG_TABLE = "teacher_usage_config"
TEACHER_USAGE_CONFIG_READ_EXPR = "rls_community_read_allowed()"
TEACHER_USAGE_CONFIG_WRITE_EXPR = "rls_platform_admin_only()"

SPLIT_POLICIES = (
    (DIAGRAMS_TABLE, DIAGRAM_READ_EXPR, DIAGRAM_WRITE_EXPR),
    (EMBEDDINGS_TABLE, EMBEDDINGS_READ_EXPR, EMBEDDINGS_WRITE_EXPR),
    (TEACHER_USAGE_CONFIG_TABLE, TEACHER_USAGE_CONFIG_READ_EXPR, TEACHER_USAGE_CONFIG_WRITE_EXPR),
)

_REPLACED_NAMES = ("tenant", "admin", "select", "write", "update", "delete")


def split_policy_tables() -> list[str]:
    """Tables this module installs."""
    return [table for table, _read, _write in SPLIT_POLICIES]


def iter_split_policies() -> list[tuple[str, str]]:
    """(table, expression) pairs for column-reference checks."""
    rows: list[tuple[str, str]] = []
    for table, read_expr, write_expr in SPLIT_POLICIES:
        rows.append((table, read_expr))
        rows.append((table, write_expr))
    return rows


def create_split_policies(table: str, read_expr: str, write_expr: str) -> None:
    """Create ``{table}_select``, ``_write`` (insert), ``_update`` and ``_delete``."""
    op.execute(sa.text(f'CREATE POLICY "{table}_select" ON "{table}" FOR SELECT USING ({read_expr})'))
    op.execute(sa.text(f'CREATE POLICY "{table}_write" ON "{table}" FOR INSERT WITH CHECK ({write_expr})'))
    op.execute(
        sa.text(
            f'CREATE POLICY "{table}_update" ON "{table}" FOR UPDATE USING ({write_expr}) WITH CHECK ({write_expr})'
        )
    )
    op.execute(sa.text(f'CREATE POLICY "{table}_delete" ON "{table}" FOR DELETE USING ({write_expr})'))


def upgrade_split_policies() -> None:
    """Replace the single policy on each table with select/insert/update/delete."""
    inspector = sa.inspect(op.get_bind())
    for table, read_expr, write_expr in SPLIT_POLICIES:
        if not inspector.has_table(table):
            continue
        op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY'))
        for suffix in _REPLACED_NAMES:
            op.execute(sa.text(f'DROP POLICY IF EXISTS "{table}_{suffix}" ON "{table}"'))
        create_split_policies(table, read_expr, write_expr)
