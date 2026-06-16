"""RLS: scope panel diagram access via rls_user_visible (not blanket panel true).

Revision ID: 0051
Revises: 0050
"""

from typing import Sequence, Union

from alembic import op

from db_rls.functions_sql import rls_functions_upgrade_statements

revision: str = "0051"
down_revision: Union[str, None] = "0050"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for statement in rls_functions_upgrade_statements():
        op.execute(statement)


def downgrade() -> None:
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
                WHEN rls_is_panel_mode() OR rls_panel_global_read() THEN true
                ELSE rls_same_org_users(owner_user_id)
            END
        $$;
        """
    )
