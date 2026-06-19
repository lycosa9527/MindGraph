"""RLS: break rls_same_org_users recursion via SECURITY DEFINER org lookup.

Revision ID: 0059
Revises: 0058

rls_same_org_users() previously queried the users table directly. Under the
users RLS policy (rls_user_visible -> rls_same_org_users), that re-applied the
same policy and recursed until "stack depth limit exceeded". The function now
compares organization ids through rls_lookup_user_organization_id(), which is
SECURITY DEFINER and therefore reads users without re-triggering RLS.
"""

from typing import Sequence, Union

from alembic import op

from db_rls.functions_sql import rls_functions_upgrade_statements

revision: str = "0059"
down_revision: Union[str, None] = "0058"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for statement in rls_functions_upgrade_statements():
        op.execute(statement)


def downgrade() -> None:
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
                AND EXISTS (
                    SELECT 1
                    FROM users viewer
                    JOIN users target ON viewer.organization_id = target.organization_id
                    WHERE viewer.id = rls_current_user_id()
                      AND target.id = target_user_id
                      AND viewer.organization_id IS NOT NULL
                )
        $$;
        """
    )
