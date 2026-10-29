"""Replace the seminar file policy and grant the members table.

The previous file policy used NOT EXISTS on mindmate_collab_members. That
table only shows the current user, so the probe is true for outsiders.
rev_0146 created the members table without the explicit app-role grant that
rev_0149 added for background files.

Revision ID: 0156
Revises: 0155
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from utils.db_rls.policy_builder import (
    MINDMATE_COLLAB_LEGACY_FILE_CHECK as MINDMATE_COLLAB_FILE_CHECK,
    MINDMATE_COLLAB_LEGACY_FILE_EXPR as MINDMATE_COLLAB_FILE_EXPR,
    _create_all_policy,
)

revision: str = "0156"
down_revision: Union[str, None] = "0155"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_FILES = "mindmate_collab_background_files"
_POLICY = "mindmate_collab_background_files_tenant"

_SESSION = (
    "EXISTS (SELECT 1 FROM mindmate_collab_sessions s WHERE s.id = session_id AND ("
    "s.owner_user_id = rls_current_user_id() "
    "OR (s.visibility = 'network' AND rls_community_read_allowed()) "
    "OR (s.organization_id IS NOT NULL AND rls_org_visible(s.organization_id)) "
    "OR rls_user_bound_to_org(s.owner_user_id, rls_current_org_id()) "
    "OR rls_platform_admin_only() "
    "OR rls_is_system_mode()"
    "))"
)
_MEMBER_BEFORE = (
    "NOT EXISTS (SELECT 1 FROM mindmate_collab_members m WHERE m.session_id = session_id) "
    "OR EXISTS (SELECT 1 FROM mindmate_collab_members m "
    "WHERE m.session_id = session_id AND m.user_id = rls_current_user_id()) "
    "OR EXISTS (SELECT 1 FROM mindmate_collab_sessions s "
    "WHERE s.id = session_id AND s.owner_user_id = rls_current_user_id())"
)
_EXPR_BEFORE = "rls_is_system_mode() OR rls_platform_admin_only() OR (" + _SESSION + " AND (" + _MEMBER_BEFORE + "))"
_CHECK_BEFORE = (
    "(" + _EXPR_BEFORE + ") AND (uploader_user_id = rls_current_user_id() "
    "OR rls_is_system_mode() OR rls_platform_admin_only())"
)


def _grant_members() -> None:
    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mindgraph_app')
                   AND EXISTS (
                       SELECT 1 FROM information_schema.tables
                       WHERE table_schema = 'public' AND table_name = 'mindmate_collab_members'
                   ) THEN
                    GRANT SELECT, INSERT, UPDATE, DELETE
                    ON TABLE mindmate_collab_members TO mindgraph_app;
                END IF;
            END $$;
            """
        )
    )


def upgrade() -> None:
    _create_all_policy(_FILES, _POLICY, MINDMATE_COLLAB_FILE_EXPR, MINDMATE_COLLAB_FILE_CHECK)
    _grant_members()


def downgrade() -> None:
    _create_all_policy(_FILES, _POLICY, _EXPR_BEFORE, _CHECK_BEFORE)
