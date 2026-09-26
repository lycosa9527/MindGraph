"""RLS for tables that were created after the greenfield policy groups.

Login and collectors keep working under system mode. School members do not
see another organization's secrets, staff links, or preview specs.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

ERROR_TABLES = ("error_groups", "error_events")
ERROR_EXPR = "rls_is_system_mode() OR (rls_is_panel_mode() AND rls_panel_global_read())"

THINKING_CATALOG_TABLES = ("thinking_coin_earn_tasks", "thinking_coin_settings")
THINKING_CATALOG_READ = "rls_community_read_allowed()"
THINKING_CATALOG_WRITE = "rls_is_system_mode() OR (rls_is_panel_mode() AND rls_panel_global_read())"

OAUTH_CONFIG_TABLE = "organization_oauth_configs"
OAUTH_CONFIG_READ = "rls_is_system_mode() OR rls_org_visible(organization_id)"
OAUTH_CONFIG_WRITE = "rls_is_system_mode() OR (rls_is_panel_mode() AND rls_panel_global_read())"

OAUTH_LINK_TABLE = "oauth_user_links"
OAUTH_LINK_EXPR = (
    "rls_is_system_mode() "
    "OR user_id = rls_current_user_id() "
    "OR (rls_is_panel_mode() AND rls_org_visible(organization_id))"
)

STAFF_LINK_TABLE = "dingtalk_staff_links"
STAFF_LINK_READ = "rls_is_system_mode() OR rls_org_visible(organization_id) OR user_id = rls_current_user_id()"
STAFF_LINK_WRITE = (
    "rls_is_system_mode() "
    "OR user_id = rls_current_user_id() "
    "OR (rls_is_panel_mode() AND rls_org_visible(organization_id))"
)

PREVIEW_TABLE = "generation_preview_links"
PREVIEW_EXPR = (
    "rls_is_system_mode() "
    "OR user_id = rls_current_user_id() "
    "OR (rls_is_panel_mode() AND ("
    "rls_panel_global_read() "
    "OR rls_org_visible(organization_id) "
    "OR rls_org_visible(rls_lookup_user_organization_id(user_id))"
    "))"
)

_SPLIT_POLICIES = (
    (THINKING_CATALOG_TABLES, THINKING_CATALOG_READ, THINKING_CATALOG_WRITE),
    ((OAUTH_CONFIG_TABLE,), OAUTH_CONFIG_READ, OAUTH_CONFIG_WRITE),
    ((STAFF_LINK_TABLE,), STAFF_LINK_READ, STAFF_LINK_WRITE),
)
_ALL_POLICIES = (
    (ERROR_TABLES, ERROR_EXPR),
    ((OAUTH_LINK_TABLE,), OAUTH_LINK_EXPR),
    ((PREVIEW_TABLE,), PREVIEW_EXPR),
)


def iter_gap_table_policies() -> list[tuple[str, str]]:
    """(table, expression) pairs for column-reference checks."""
    rows: list[tuple[str, str]] = []
    for tables, read_expr, write_expr in _SPLIT_POLICIES:
        for table in tables:
            rows.append((table, read_expr))
            rows.append((table, write_expr))
    for tables, expr in _ALL_POLICIES:
        for table in tables:
            rows.append((table, expr))
    return rows


def _enable_force(table: str) -> None:
    op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
    op.execute(sa.text(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY'))


def _drop_named(table: str) -> None:
    for suffix in ("tenant", "select", "write", "update", "delete"):
        op.execute(sa.text(f'DROP POLICY IF EXISTS "{table}_{suffix}" ON "{table}"'))


def _create_all(table: str, expr: str) -> None:
    _drop_named(table)
    op.execute(sa.text(f'CREATE POLICY "{table}_tenant" ON "{table}" FOR ALL USING ({expr}) WITH CHECK ({expr})'))


def _create_split(table: str, read_expr: str, write_expr: str) -> None:
    _drop_named(table)
    op.execute(sa.text(f'CREATE POLICY "{table}_select" ON "{table}" FOR SELECT USING ({read_expr})'))
    op.execute(sa.text(f'CREATE POLICY "{table}_write" ON "{table}" FOR INSERT WITH CHECK ({write_expr})'))
    op.execute(
        sa.text(
            f'CREATE POLICY "{table}_update" ON "{table}" FOR UPDATE USING ({write_expr}) WITH CHECK ({write_expr})'
        )
    )
    op.execute(sa.text(f'CREATE POLICY "{table}_delete" ON "{table}" FOR DELETE USING ({write_expr})'))


def _disable(table: str) -> None:
    _drop_named(table)
    op.execute(sa.text(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY'))


def upgrade_gap_policies() -> None:
    """Enable forced RLS on the previously unprotected tables."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for tables, read_expr, write_expr in _SPLIT_POLICIES:
        for table in tables:
            if not inspector.has_table(table):
                continue
            _enable_force(table)
            _create_split(table, read_expr, write_expr)
    for tables, expr in _ALL_POLICIES:
        for table in tables:
            if not inspector.has_table(table):
                continue
            _enable_force(table)
            _create_all(table, expr)


def downgrade_gap_policies() -> None:
    """Remove the gap-table policies."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    names = [table for tables, _read, _write in _SPLIT_POLICIES for table in tables]
    names.extend(table for tables, _expr in _ALL_POLICIES for table in tables)
    for table in names:
        if inspector.has_table(table):
            _disable(table)
