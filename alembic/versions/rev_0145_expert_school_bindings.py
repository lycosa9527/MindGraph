"""Experts may be bound to many schools, including schools they create.

Revision ID: 0145
Revises: 0144
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from utils.db_rls.functions_sql import (
    build_grant_rls_functions_to_app_sql,
    rls_functions_upgrade_statements,
)
from utils.db_rls.policy_builder import (
    MINDMATE_COLLAB_MESSAGE_EXPR,
    MINDMATE_COLLAB_READ_CHECK,
    MINDMATE_COLLAB_READ_EXPR,
    MINDMATE_COLLAB_SESSION_CHECK,
    MINDMATE_COLLAB_SESSION_EXPR,
    USERS_EXPR,
    _create_all_policy,
    _drop_policy,
)

revision: str = "0145"
down_revision: Union[str, None] = "0144"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "organization_expert_bindings"

_SELECT_EXPR = (
    "rls_is_system_mode() OR rls_is_dashboard_mode() OR rls_panel_global_read() "
    "OR user_id = rls_current_user_id() "
    "OR rls_org_visible(organization_id) "
    "OR (rls_is_panel_mode() AND rls_panel_org_invited_by_actor("
    "rls_lookup_org_invited_by_user_id(organization_id)))"
)
_WRITE_EXPR = (
    "rls_is_system_mode() OR rls_is_dashboard_mode() OR rls_panel_global_read() "
    "OR (rls_is_panel_mode() AND user_id = rls_current_user_id() "
    "AND rls_panel_org_invited_by_actor(rls_lookup_org_invited_by_user_id(organization_id)))"
)

_SESSION_EXPR_BEFORE = (
    "owner_user_id = rls_current_user_id() "
    "OR (visibility = 'network' AND rls_community_read_allowed()) "
    "OR (organization_id IS NOT NULL AND rls_org_visible(organization_id)) "
    "OR rls_platform_admin_only() "
    "OR rls_is_system_mode()"
)
_MESSAGE_EXPR_BEFORE = (
    "EXISTS (SELECT 1 FROM mindmate_collab_sessions s WHERE s.id = session_id AND ("
    "s.owner_user_id = rls_current_user_id() "
    "OR (s.visibility = 'network' AND rls_community_read_allowed()) "
    "OR (s.organization_id IS NOT NULL AND rls_org_visible(s.organization_id)) "
    "OR rls_platform_admin_only() "
    "OR rls_is_system_mode()"
    ")) AND (sender_user_id = rls_current_user_id() OR role = 'assistant' OR rls_is_system_mode())"
)
_USERS_EXPR_BEFORE = (
    "rls_user_visible(id) OR (rls_is_panel_mode() AND organization_id IS NOT NULL AND rls_org_visible(organization_id))"
)
_READ_EXPR_BEFORE = (
    "EXISTS (SELECT 1 FROM mindmate_collab_sessions s WHERE s.id = session_id AND ("
    "s.owner_user_id = rls_current_user_id() "
    "OR (s.visibility = 'network' AND rls_community_read_allowed()) "
    "OR (s.organization_id IS NOT NULL AND rls_org_visible(s.organization_id)) "
    "OR rls_platform_admin_only() "
    "OR rls_is_system_mode()"
    "))"
)


def _binding_policies() -> None:
    op.execute(sa.text(f'ALTER TABLE "{_TABLE}" ENABLE ROW LEVEL SECURITY'))
    op.execute(sa.text(f'ALTER TABLE "{_TABLE}" FORCE ROW LEVEL SECURITY'))
    op.execute(sa.text(f'CREATE POLICY "{_TABLE}_select" ON "{_TABLE}" FOR SELECT USING ({_SELECT_EXPR})'))
    op.execute(sa.text(f'CREATE POLICY "{_TABLE}_insert" ON "{_TABLE}" FOR INSERT WITH CHECK ({_WRITE_EXPR})'))
    op.execute(
        sa.text(
            f'CREATE POLICY "{_TABLE}_update" ON "{_TABLE}" FOR UPDATE USING ({_WRITE_EXPR}) WITH CHECK ({_WRITE_EXPR})'
        )
    )
    op.execute(sa.text(f'CREATE POLICY "{_TABLE}_delete" ON "{_TABLE}" FOR DELETE USING ({_WRITE_EXPR})'))


def _recreate_mindmate(session_expr: str, message_expr: str, read_expr: str, read_check: str) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    specs = (
        ("mindmate_collab_sessions", session_expr, MINDMATE_COLLAB_SESSION_CHECK),
        ("mindmate_collab_messages", message_expr, message_expr),
        ("mindmate_collab_read_cursors", read_expr, read_check),
    )
    for table, using_expr, check_expr in specs:
        if not inspector.has_table(table):
            continue
        _drop_policy(table, f"{table}_tenant")
        _create_all_policy(table, f"{table}_tenant", using_expr, check_expr)


def _recreate_users(expr: str) -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("users"):
        return
    _drop_policy("users", "users_tenant")
    _create_all_policy("users", "users_tenant", expr)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(_TABLE):
        op.create_table(
            _TABLE,
            sa.Column("organization_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("organization_id", "user_id"),
        )
        op.create_index(f"ix_{_TABLE}_user_id", _TABLE, ["user_id"])
        op.execute(
            sa.text(
                f"INSERT INTO {_TABLE} (organization_id, user_id, created_at) "
                "SELECT o.id, o.invited_by_user_id, NOW() "
                "FROM organizations o "
                "JOIN users u ON u.id = o.invited_by_user_id "
                "WHERE u.role = 'expert'"
            )
        )
        _binding_policies()
    for statement in rls_functions_upgrade_statements():
        op.execute(statement)
    op.execute(build_grant_rls_functions_to_app_sql())
    _recreate_users(USERS_EXPR)
    _recreate_mindmate(
        MINDMATE_COLLAB_SESSION_EXPR,
        MINDMATE_COLLAB_MESSAGE_EXPR,
        MINDMATE_COLLAB_READ_EXPR,
        MINDMATE_COLLAB_READ_CHECK,
    )


def downgrade() -> None:
    _recreate_users(_USERS_EXPR_BEFORE)
    _recreate_mindmate(
        _SESSION_EXPR_BEFORE,
        _MESSAGE_EXPR_BEFORE,
        _READ_EXPR_BEFORE,
        _READ_EXPR_BEFORE + " AND (user_id = rls_current_user_id() OR rls_is_system_mode())",
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION rls_same_org_users(target_user_id bigint)
        RETURNS boolean
        LANGUAGE sql
        STABLE
        PARALLEL SAFE
        AS $$
            SELECT target_user_id IS NOT NULL
                AND rls_current_user_id() IS NOT NULL
                AND rls_lookup_user_organization_id(rls_current_user_id()) IS NOT NULL
                AND rls_lookup_user_organization_id(target_user_id)
                    = rls_lookup_user_organization_id(rls_current_user_id())
        $$;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION rls_chat_channel_visible(channel_org_id bigint)
        RETURNS boolean
        LANGUAGE sql
        STABLE
        PARALLEL SAFE
        AS $$
            SELECT CASE
                WHEN rls_is_system_mode() THEN true
                WHEN rls_is_deny_mode() THEN false
                WHEN channel_org_id IS NULL THEN rls_allow_global_channels() OR rls_is_panel_mode()
                ELSE rls_org_visible(channel_org_id)
            END
        $$;
        """
    )
    bind = op.get_bind()
    if sa.inspect(bind).has_table(_TABLE):
        op.drop_table(_TABLE)
    op.execute("DROP FUNCTION IF EXISTS rls_actor_bound_to_org(bigint);")
    op.execute("DROP FUNCTION IF EXISTS rls_users_share_bound_org(bigint, bigint);")
    op.execute("DROP FUNCTION IF EXISTS rls_user_bound_to_org(bigint, bigint);")
