"""Qualify Learning Space RLS joins so membership/student rows match the class.

Revision ID: 0127
Revises: 0126
Create Date: 2026-09-19
"""

from typing import Sequence, Union

from utils.db_rls.policy_builder import upgrade_learning_space_policies

revision: str = "0127"
down_revision: Union[str, None] = "0126"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    upgrade_learning_space_policies()


def downgrade() -> None:
    return
