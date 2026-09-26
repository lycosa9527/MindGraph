"""RLS for tables created without policies.

Covers OAuth secrets and links, DingTalk staff links, generation preview
specs, admin error logs, and the thinking-coin task catalog.

Revision ID: 0131
Revises: 0130
"""

from typing import Sequence, Union

from utils.db_rls.gap_policies import downgrade_gap_policies, upgrade_gap_policies

revision: str = "0131"
down_revision: Union[str, None] = "0130"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    upgrade_gap_policies()


def downgrade() -> None:
    downgrade_gap_policies()
