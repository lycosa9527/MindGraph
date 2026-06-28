"""RLS: allow panel experts to INSERT organizations they invite (invited_by_user_id).

Revision ID: 0072
Revises: 0071
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from db_rls.functions_sql import rls_functions_upgrade_statements
from db_rls.policy_builder import ORGS_EXPR, _create_all_policy, _drop_policy

revision: str = "0072"
down_revision: Union[str, None] = "0071"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ORGS_EXPR_BEFORE = (
    "(rls_mode() = 'public' AND rls_allow_public_org_list()) "
    "OR rls_org_visible(id) "
    "OR (rls_is_panel_mode() AND (rls_panel_global_read() OR rls_org_id_in_readable_list(id) "
    "OR rls_panel_legacy_org_visible(id)))"
)


def upgrade() -> None:
    for statement in rls_functions_upgrade_statements():
        op.execute(statement)
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("organizations"):
        return
    _drop_policy("organizations", "organizations_tenant")
    _create_all_policy("organizations", "organizations_tenant", ORGS_EXPR)


def downgrade() -> None:
    bind = op.get_bind()
    if sa.inspect(bind).has_table("organizations"):
        _drop_policy("organizations", "organizations_tenant")
        _create_all_policy("organizations", "organizations_tenant", _ORGS_EXPR_BEFORE)
    op.execute("DROP FUNCTION IF EXISTS rls_panel_org_invited_by_actor(bigint);")
