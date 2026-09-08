"""Detach 系统公告 from any school so RLS shows it in every org.

Revision ID: 0114
Revises: 0113
Create Date: 2026-09-07
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0114"
down_revision: Union[str, None] = "0113"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "chat_channels"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(_TABLE):
        return
    op.execute(
        sa.text(
            """
            UPDATE chat_channels
            SET organization_id = NULL
            WHERE channel_type = 'announce'
              AND organization_id IS NOT NULL
            """
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(_TABLE):
        return
