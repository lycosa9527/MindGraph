"""RLS: org legacy check without organizations-policy recursion.

Revision ID: 0053
Revises: 0052
"""

from typing import Sequence, Union

from alembic import op

from db_rls.functions_sql import rls_functions_upgrade_statements

revision: str = "0053"
down_revision: Union[str, None] = "0052"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for statement in rls_functions_upgrade_statements():
        op.execute(statement)


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS rls_lookup_org_invited_by_user_id(bigint);")
    op.execute(
        """
        CREATE OR REPLACE FUNCTION rls_panel_legacy_org_visible(target_org_id bigint)
        RETURNS boolean
        LANGUAGE sql
        STABLE
        PARALLEL SAFE
        AS $$
            SELECT coalesce(rls_setting_text('app.role'), '') <> 'expert'
                AND EXISTS (
                    SELECT 1 FROM organizations o
                    WHERE o.id = target_org_id
                      AND o.invited_by_user_id IS NULL
                )
        $$;
        """
    )
