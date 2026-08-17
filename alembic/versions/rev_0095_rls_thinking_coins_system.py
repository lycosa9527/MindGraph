"""RLS: allow system mode on thinking-coin user tables.

Admin case-approve credits the author under that user's RLS context (not
panel). System mode covers privileged cleanup (user delete) without granting
panel routes blanket wallet write access.

Revision ID: 0095
Revises: 0094
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from utils.db_rls.policy_builder import _create_all_policy, _drop_policy

revision: str = "0095"
down_revision: Union[str, None] = "0094"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_USER_OWNED_TABLES = (
    "thinking_coin_wallets",
    "thinking_coin_ledger",
    "thinking_coin_checkins",
    "thinking_coin_daily_activity",
)
_LEGACY_EXPR = "user_id = rls_current_user_id()"
_EXPR = "user_id = rls_current_user_id() OR rls_is_system_mode()"


def _recreate_tenant_policy(table: str, expr: str) -> None:
    policy = f"{table}_tenant"
    _drop_policy(table, policy)
    _create_all_policy(table, policy, expr)


def upgrade() -> None:
    bind = op.get_bind()
    for table in _USER_OWNED_TABLES:
        if sa.inspect(bind).has_table(table):
            _recreate_tenant_policy(table, _EXPR)


def downgrade() -> None:
    bind = op.get_bind()
    for table in _USER_OWNED_TABLES:
        if sa.inspect(bind).has_table(table):
            _recreate_tenant_policy(table, _LEGACY_EXPR)
