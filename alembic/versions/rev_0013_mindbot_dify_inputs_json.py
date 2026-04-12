"""MindBot: optional Dify app inputs JSON per organization.

Revision ID: 0013
Revises: 0012
Create Date: 2026-04-13
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "organization_mindbot_configs",
        sa.Column("dify_inputs_json", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("organization_mindbot_configs", "dify_inputs_json")
