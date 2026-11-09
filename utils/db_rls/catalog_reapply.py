"""Install the current row-level security catalog in one idempotent pass.

``pg_dump`` archives include ``ENABLE ROW LEVEL SECURITY`` and ``CREATE POLICY``.
A restore whose ``alembic_version`` is already head does not replay the
revisions that first created those policies. Revision 0167 calls
``reapply_current_rls_policies`` so a 0166 restore still ends with the catalog;
revision 0169 calls it again to install the tightened scope.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from utils.db_rls.functions_sql import build_grant_rls_functions_to_app_sql, rls_functions_upgrade_statements
from utils.db_rls.gap_policies import iter_gap_table_policies, upgrade_gap_policies
from utils.db_rls.policy_builder import (
    CANVAS_INPUT_DEVICE_EXPR,
    CLIENT_SHELL_DEVICE_EXPR,
    MAITE_CHILD_TABLES,
    MAITE_TASK_REFERENCE_EXPR,
    MINDMATE_COLLAB_FILE_CHECK,
    MINDMATE_COLLAB_FILE_EXPR,
    MINDMATE_COLLAB_MEMBER_EXPR,
    USER_OWNED_EXPR,
    all_rls_tables,
    downgrade_policies_for_tables,
    upgrade_group_a,
    upgrade_group_b,
    upgrade_group_cde,
    upgrade_learning_space_policies,
    upgrade_mindmate_seminar_policies,
)
from utils.db_rls.split_policies import create_split_policies, upgrade_split_policies

_USER_OR_STAFF = "user_id = rls_current_user_id() OR rls_platform_admin_only()"
_SYSTEM_ACCESS = "rls_is_system_mode()"
_COMMUNITY_READ = "rls_community_read_allowed()"
_PANEL_WRITE = "rls_is_panel_mode()"
_AUTHOR_OR_PANEL = "author_id = rls_current_user_id() OR rls_is_panel_mode() OR rls_is_system_mode()"
_USER_OR_SYSTEM = "user_id = rls_current_user_id() OR rls_is_system_mode()"
_ZHIHUI_ACCESS = "rls_platform_admin_only()"
_EXPORT_ACCESS = "created_by_user_id = rls_current_user_id() OR rls_platform_admin_only()"
_ADMIN_SELECT = (
    "rls_is_system_mode() OR ("
    "rls_is_panel_mode() AND coalesce(rls_setting_text('app.role'), '') IN ('superadmin', 'admin')"
    ")"
)
_SHARE_ACCESS = (
    "grantee_user_id = rls_current_user_id() "
    "OR shared_by_user_id = rls_current_user_id() "
    "OR EXISTS ("
    "SELECT 1 FROM diagrams d "
    "WHERE d.id = diagram_id AND d.user_id = rls_current_user_id()"
    ") "
    "OR rls_platform_admin_only()"
)
_COVER_WRITE = (
    "EXISTS ("
    "SELECT 1 FROM case_square_posts p "
    "WHERE p.id = post_id AND ("
    "p.author_id = rls_current_user_id() "
    "OR rls_is_panel_mode() "
    "OR rls_is_system_mode()"
    "))"
)
_EXPERT_SELECT = (
    "rls_is_system_mode() OR rls_is_dashboard_mode() OR rls_panel_global_read() "
    "OR user_id = rls_current_user_id() "
    "OR rls_org_visible(organization_id) "
    "OR (rls_is_panel_mode() AND rls_panel_org_invited_by_actor("
    "rls_lookup_org_invited_by_user_id(organization_id)))"
)
_EXPERT_WRITE = (
    "rls_is_system_mode() OR rls_panel_global_read() "
    "OR (rls_is_panel_mode() AND user_id = rls_current_user_id() "
    "AND rls_panel_org_invited_by_actor(rls_lookup_org_invited_by_user_id(organization_id)))"
)

_FOLDER_TABLES = (
    "diagram_folders",
    "mindmate_folders",
    "mindmate_conversation_folders",
    "user_library_demos",
)
_SYSTEM_TABLES = (
    "user_dropdown_items",
    "vod_folders",
    "vod_media",
    "training_courses",
    "training_course_steps",
    "training_course_assets",
    "training_course_completions",
)
_CLASSROOM_TABLES = ("mind_classroom_jobs", "mind_classroom_slides")
_ZHIHUI_TABLES = ("zhihui_conversations", "zhihui_generations")
_COIN_TABLES = (
    "thinking_coin_wallets",
    "thinking_coin_ledger",
    "thinking_coin_checkins",
    "thinking_coin_daily_activity",
)
_MAITE_USER_TABLES = (
    "maite_problems",
    "maite_inquiry_sessions",
    "maite_graph_node_progress",
    "maite_prompt_runs",
)
# Showcase staff may be delegated non-admin users; their panel session is the gate.
_STAFF_GRANT_TABLE = "case_square_staff_grants"
_STAFF_GRANT_READ = "user_id = rls_current_user_id() OR rls_is_panel_mode() OR rls_is_system_mode()"
_AUDIT_TABLE = "case_square_audit_log"

_ONE_OFF_TABLES = (
    "admin_activity_log",
    "canvas_input_devices",
    "client_shell_devices",
    "case_square_audit_log",
    "case_square_cover_jobs",
    "case_square_field_options",
    "case_square_post_favorites",
    "case_square_post_likes",
    "case_square_posts",
    "case_square_staff_grants",
    *_FOLDER_TABLES,
    "diagram_shares",
    *_CLASSROOM_TABLES,
    "mindmate_seminar_background_files",
    "mindmate_seminar_members",
    "organization_expert_bindings",
    *_COIN_TABLES,
    *_SYSTEM_TABLES,
    *_MAITE_USER_TABLES,
    *(table for table, _expr in MAITE_CHILD_TABLES),
    "maite_task_references",
    *_ZHIHUI_TABLES,
)


def catalog_table_names() -> frozenset[str]:
    """Tables whose policies this module drops and installs."""
    names = set(all_rls_tables())
    names.update(table for table, _expr in iter_gap_table_policies())
    names.update(_ONE_OFF_TABLES)
    return frozenset(names)


def reapply_current_rls_policies() -> None:
    """Install the current helper functions, drop every catalog policy, then install the current expressions.

    Safe on a database that already has the policies (fresh upgrade through
    0166, or production after the seminar policies were applied by hand) and
    on a 0166 restore that has ``FORCE ROW LEVEL SECURITY`` and zero policies.
    Functions come first because current policies call helpers an older
    restore may not have.
    """
    for statement in rls_functions_upgrade_statements():
        op.execute(statement)
    op.execute(build_grant_rls_functions_to_app_sql())
    downgrade_policies_for_tables(sorted(catalog_table_names()))
    upgrade_group_a()
    upgrade_group_b()
    upgrade_group_cde()
    upgrade_mindmate_seminar_policies()
    upgrade_learning_space_policies()
    upgrade_gap_policies()
    upgrade_split_policies()
    _reapply_one_off_policies()
    op.execute(sa.text("DROP FUNCTION IF EXISTS rls_panel_legacy_org_visible(bigint)"))


def _table_ready(table: str) -> bool:
    if not sa.inspect(op.get_bind()).has_table(table):
        return False
    op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
    op.execute(sa.text(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY'))
    return True


def _policy_all(table: str, name: str, using_expr: str, check_expr: str | None = None) -> None:
    if not _table_ready(table):
        return
    check_sql = using_expr if check_expr is None else check_expr
    op.execute(sa.text(f'CREATE POLICY "{name}" ON "{table}" FOR ALL USING ({using_expr}) WITH CHECK ({check_sql})'))


def _policy_split(table: str, read_expr: str, write_expr: str) -> None:
    if _table_ready(table):
        create_split_policies(table, read_expr, write_expr)


def _reapply_one_off_policies() -> None:
    _policy_all("canvas_input_devices", "canvas_input_devices_tenant", CANVAS_INPUT_DEVICE_EXPR)
    _policy_all("client_shell_devices", "client_shell_devices_tenant", CLIENT_SHELL_DEVICE_EXPR)
    _policy_all("mindmate_export_jobs", "mindmate_export_jobs_access", _EXPORT_ACCESS)
    _policy_all("mindmate_seminar_members", "mindmate_seminar_members_tenant", MINDMATE_COLLAB_MEMBER_EXPR)
    _policy_all(
        "mindmate_seminar_background_files",
        "mindmate_seminar_background_files_tenant",
        MINDMATE_COLLAB_FILE_EXPR,
        MINDMATE_COLLAB_FILE_CHECK,
    )
    _policy_all("diagram_shares", "diagram_shares_all", _SHARE_ACCESS)
    for table in _FOLDER_TABLES:
        _policy_split(table, _USER_OR_STAFF, _USER_OR_STAFF)
    for table in _SYSTEM_TABLES:
        _policy_split(table, _SYSTEM_ACCESS, _SYSTEM_ACCESS)
    for table in _CLASSROOM_TABLES:
        _policy_all(table, f"{table}_access", _USER_OR_SYSTEM)
    for table in _ZHIHUI_TABLES:
        _policy_split(table, _ZHIHUI_ACCESS, _ZHIHUI_ACCESS)
    for table in _COIN_TABLES:
        _policy_all(table, f"{table}_tenant", _USER_OR_SYSTEM)
    for table in _MAITE_USER_TABLES:
        _policy_all(table, f"{table}_tenant", USER_OWNED_EXPR)
    for table, expr in MAITE_CHILD_TABLES:
        _policy_all(table, f"{table}_tenant", expr)
    _policy_all("maite_task_references", "maite_task_references_tenant", MAITE_TASK_REFERENCE_EXPR)
    _policy_split("case_square_posts", _COMMUNITY_READ, _AUTHOR_OR_PANEL)
    _policy_split("case_square_post_likes", _COMMUNITY_READ, _USER_OR_STAFF)
    _policy_split("case_square_post_favorites", _COMMUNITY_READ, _USER_OR_STAFF)
    _policy_split("case_square_cover_jobs", _COMMUNITY_READ, _COVER_WRITE)
    _policy_split("case_square_field_options", _COMMUNITY_READ, _PANEL_WRITE)
    _policy_split(_STAFF_GRANT_TABLE, _STAFF_GRANT_READ, _PANEL_WRITE)
    _policy_split(_AUDIT_TABLE, _PANEL_WRITE, _PANEL_WRITE)
    _reapply_admin_activity()
    _reapply_expert_bindings()


def _reapply_admin_activity() -> None:
    table = "admin_activity_log"
    if not _table_ready(table):
        return
    op.execute(sa.text(f'CREATE POLICY "{table}_select" ON "{table}" FOR SELECT USING ({_ADMIN_SELECT})'))
    op.execute(sa.text(f'CREATE POLICY "{table}_insert" ON "{table}" FOR INSERT WITH CHECK ({_SYSTEM_ACCESS})'))


def _reapply_expert_bindings() -> None:
    table = "organization_expert_bindings"
    if not _table_ready(table):
        return
    op.execute(sa.text(f'CREATE POLICY "{table}_select" ON "{table}" FOR SELECT USING ({_EXPERT_SELECT})'))
    op.execute(sa.text(f'CREATE POLICY "{table}_insert" ON "{table}" FOR INSERT WITH CHECK ({_EXPERT_WRITE})'))
    op.execute(
        sa.text(
            f'CREATE POLICY "{table}_update" ON "{table}" FOR UPDATE '
            f"USING ({_EXPERT_WRITE}) WITH CHECK ({_EXPERT_WRITE})"
        )
    )
    op.execute(sa.text(f'CREATE POLICY "{table}_delete" ON "{table}" FOR DELETE USING ({_EXPERT_WRITE})'))
