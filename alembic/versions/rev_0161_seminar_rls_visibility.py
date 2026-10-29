"""Seminar row security follows the invite list.

Member RLS hides every seat except the caller's, so a policy cannot ask
whether any seat is invited. This function runs as the table owner and
can see the whole roster. An open school seminar stays visible to that
school. A closed or public seminar is visible to the host and to teachers
who accepted an invite.

Revision ID: 0161
Revises: 0160
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from utils.db_rls.policy_builder import (
    MINDMATE_COLLAB_FILE_CHECK,
    MINDMATE_COLLAB_FILE_EXPR,
    MINDMATE_SEMINAR_FILE_CHECK_BEFORE_VISIBILITY,
    MINDMATE_SEMINAR_FILE_EXPR_BEFORE_VISIBILITY,
    MINDMATE_SEMINAR_TABLES_BEFORE_VISIBILITY,
    upgrade_mindmate_seminar_policies,
    _create_all_policy,
    downgrade_policies_for_tables,
)

revision: str = "0161"
down_revision: Union[str, None] = "0160"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_FUNCTION = "rls_seminar_session_visible"
_FILES = "mindmate_seminar_background_files"

_CREATE = sa.text(
    """
    CREATE OR REPLACE FUNCTION rls_seminar_session_visible(target_session_id text)
    RETURNS boolean
    LANGUAGE sql
    STABLE
    SECURITY DEFINER
    SET search_path = public
    AS $$
        SELECT EXISTS (
            SELECT 1
            FROM mindmate_seminar_sessions AS seminar
            WHERE seminar.id = target_session_id
              AND (
                rls_is_system_mode()
                OR rls_platform_admin_only()
                OR seminar.owner_user_id = rls_current_user_id()
                OR EXISTS (
                    SELECT 1
                    FROM mindmate_seminar_members AS member
                    WHERE member.session_id = seminar.id
                      AND member.user_id = rls_current_user_id()
                      AND member.accepted
                      AND member.invited
                      AND member.left_at IS NULL
                )
                OR (
                    seminar.visibility = 'organization'
                    AND seminar.organization_id IS NOT NULL
                    AND seminar.ended_at IS NULL
                    AND NOT EXISTS (
                        SELECT 1
                        FROM mindmate_seminar_members AS member
                        WHERE member.session_id = seminar.id
                          AND member.invited
                    )
                    AND NOT EXISTS (
                        SELECT 1
                        FROM mindmate_seminar_members AS member
                        WHERE member.session_id = seminar.id
                          AND member.user_id = rls_current_user_id()
                          AND member.left_at IS NOT NULL
                    )
                    AND (
                        rls_org_visible(seminar.organization_id)
                        OR rls_user_bound_to_org(seminar.owner_user_id, rls_current_org_id())
                    )
                )
              )
        )
    $$
    """
)

_GRANT = sa.text(
    """
    DO $$
    BEGIN
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mindgraph_app') THEN
            GRANT EXECUTE ON FUNCTION rls_seminar_session_visible(text) TO mindgraph_app;
        END IF;
    END $$;
    """
)


def _reapply_files(using_expr: str, check_expr: str) -> None:
    if not sa.inspect(op.get_bind()).has_table(_FILES):
        return
    downgrade_policies_for_tables([_FILES])
    op.execute(sa.text(f'ALTER TABLE "{_FILES}" ENABLE ROW LEVEL SECURITY'))
    op.execute(sa.text(f'ALTER TABLE "{_FILES}" FORCE ROW LEVEL SECURITY'))
    _create_all_policy(_FILES, f"{_FILES}_tenant", using_expr, check_expr)


def _reapply_before_visibility() -> None:
    inspector = sa.inspect(op.get_bind())
    for table, using_expr, check_expr in MINDMATE_SEMINAR_TABLES_BEFORE_VISIBILITY:
        if not inspector.has_table(table):
            continue
        downgrade_policies_for_tables([table])
        op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY'))
        _create_all_policy(table, f"{table}_tenant", using_expr, check_expr)
    _reapply_files(
        MINDMATE_SEMINAR_FILE_EXPR_BEFORE_VISIBILITY,
        MINDMATE_SEMINAR_FILE_CHECK_BEFORE_VISIBILITY,
    )


def upgrade() -> None:
    op.execute(_CREATE)
    op.execute(_GRANT)
    upgrade_mindmate_seminar_policies()
    _reapply_files(MINDMATE_COLLAB_FILE_EXPR, MINDMATE_COLLAB_FILE_CHECK)


def downgrade() -> None:
    _reapply_before_visibility()
    op.execute(sa.text(f"DROP FUNCTION IF EXISTS {_FUNCTION}(text)"))
