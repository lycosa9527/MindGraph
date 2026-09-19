"""Tighten Learning Space panel RLS so school admins cannot see other schools.

Revision ID: 0126
Revises: 0125
Create Date: 2026-09-19
"""

from typing import Sequence, Union

from utils.db_rls.policy_builder import upgrade_learning_space_policies

revision: str = "0126"
down_revision: Union[str, None] = "0125"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    upgrade_learning_space_policies()


def downgrade() -> None:
    return
