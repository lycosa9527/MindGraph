"""Seed daily earn cap global setting."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0067"
down_revision: Union[str, None] = "0066"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Insert daily_earn_cap when missing (existing deployments after 0065)."""
    conn = op.get_bind()
    exists = conn.execute(
        sa.text("SELECT 1 FROM thinking_coin_settings WHERE key = 'daily_earn_cap'")
    ).scalar()
    if exists is None:
        op.execute(
            sa.text(
                "INSERT INTO thinking_coin_settings (key, value_int, value_text) "
                "VALUES ('daily_earn_cap', 100, NULL)"
            )
        )


def downgrade() -> None:
    """Remove daily earn cap setting."""
    op.execute(sa.text("DELETE FROM thinking_coin_settings WHERE key = 'daily_earn_cap'"))
