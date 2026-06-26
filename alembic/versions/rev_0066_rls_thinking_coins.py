"""RLS for thinking coin user-owned tables (wallet, ledger, check-in, daily activity)."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0066"
down_revision: Union[str, None] = "0065"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_USER_OWNED_TABLES = (
    "thinking_coin_wallets",
    "thinking_coin_ledger",
    "thinking_coin_checkins",
    "thinking_coin_daily_activity",
)
_EXPR = "user_id = rls_current_user_id()"


def _enable_user_policy(table: str) -> None:
    policy = f"{table}_tenant"
    op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
    op.execute(sa.text(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY'))
    op.execute(sa.text(f'CREATE POLICY "{policy}" ON "{table}" FOR ALL USING ({_EXPR}) WITH CHECK ({_EXPR})'))


def upgrade() -> None:
    bind = op.get_bind()
    for table in _USER_OWNED_TABLES:
        if sa.inspect(bind).has_table(table):
            _enable_user_policy(table)


def downgrade() -> None:
    bind = op.get_bind()
    for table in _USER_OWNED_TABLES:
        if not sa.inspect(bind).has_table(table):
            continue
        policy = f"{table}_tenant"
        op.execute(sa.text(f'DROP POLICY IF EXISTS "{policy}" ON "{table}"'))
        op.execute(sa.text(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY'))
