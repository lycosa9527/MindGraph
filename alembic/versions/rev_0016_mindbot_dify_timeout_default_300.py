"""MindBot: default dify_timeout_seconds 300 (5 minutes).

Revision ID: 0016
Revises: 0015
Create Date: 2026-04-13
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "organization_mindbot_configs",
        "dify_timeout_seconds",
        existing_type=sa.Integer(),
        nullable=False,
        server_default="300",
    )


def downgrade() -> None:
    op.alter_column(
        "organization_mindbot_configs",
        "dify_timeout_seconds",
        existing_type=sa.Integer(),
        nullable=False,
        server_default="30",
    )
