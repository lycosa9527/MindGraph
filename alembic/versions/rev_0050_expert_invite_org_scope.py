"""RLS: experts see only orgs they created on invite tab (no legacy NULL orgs).

Revision ID: 0050
Revises: 0049
"""

from typing import Sequence, Union

from alembic import op

from db_rls.functions_sql import rls_functions_upgrade_statements

revision: str = "0050"
down_revision: Union[str, None] = "0049"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for statement in rls_functions_upgrade_statements():
        op.execute(statement)


def downgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION rls_panel_legacy_org_visible(target_org_id bigint)
        RETURNS boolean
        LANGUAGE sql
        STABLE
        PARALLEL SAFE
        AS $$
            SELECT EXISTS (
                SELECT 1 FROM organizations o
                WHERE o.id = target_org_id
                  AND o.invited_by_user_id IS NULL
            )
        $$;
        """
    )
