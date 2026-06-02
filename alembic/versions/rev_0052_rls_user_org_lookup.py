"""RLS: avoid users-policy recursion via SECURITY DEFINER org lookup.

Revision ID: 0052
Revises: 0051
"""

from typing import Sequence, Union

from alembic import op

from alembic.rls_functions_sql import rls_functions_upgrade_statements

revision: str = "0052"
down_revision: Union[str, None] = "0051"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for statement in rls_functions_upgrade_statements():
        op.execute(statement)


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS rls_lookup_user_organization_id(bigint);")
    op.execute(
        """
        CREATE OR REPLACE FUNCTION rls_user_visible(target_user_id bigint)
        RETURNS boolean
        LANGUAGE sql
        STABLE
        PARALLEL SAFE
        AS $$
            SELECT CASE
                WHEN rls_is_system_mode() OR rls_is_dashboard_mode() THEN true
                WHEN rls_is_deny_mode() THEN false
                WHEN target_user_id IS NULL THEN false
                WHEN target_user_id = rls_current_user_id() THEN true
                WHEN rls_is_panel_mode() THEN (
                    rls_panel_global_read()
                    OR EXISTS (
                        SELECT 1 FROM users u
                        WHERE u.id = target_user_id
                          AND rls_org_visible(u.organization_id)
                    )
                )
                ELSE rls_same_org_users(target_user_id)
            END
        $$;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION rls_diagram_visible(owner_user_id bigint)
        RETURNS boolean
        LANGUAGE sql
        STABLE
        PARALLEL SAFE
        AS $$
            SELECT CASE
                WHEN rls_is_system_mode() THEN true
                WHEN rls_is_deny_mode() THEN false
                WHEN owner_user_id = rls_current_user_id() THEN true
                WHEN rls_panel_global_read() THEN true
                WHEN rls_is_panel_mode() THEN rls_user_visible(owner_user_id)
                ELSE rls_same_org_users(owner_user_id)
            END
        $$;
        """
    )
