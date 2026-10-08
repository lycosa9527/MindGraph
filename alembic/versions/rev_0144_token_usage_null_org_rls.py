"""Allow personal accounts to insert token_usage rows with no organization.

Kitty voice records usage and debits coins in one RLS transaction. A null
organization_id failed rls_org_visible, so the debit rolled back with it.

Revision ID: 0144
Revises: 0143
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from utils.db_rls.policy_builder import ORG_EXPR, TOKEN_USAGE_EXPR, _create_all_policy, _drop_policy

revision: str = "0144"
down_revision: Union[str, None] = "0143"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "token_usage"
_POLICY = "token_usage_tenant"


def _recreate(expr: str) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(_TABLE):
        return
    _drop_policy(_TABLE, _POLICY)
    _create_all_policy(_TABLE, _POLICY, expr)


def upgrade() -> None:
    _recreate(TOKEN_USAGE_EXPR)


def downgrade() -> None:
    _recreate(ORG_EXPR)
