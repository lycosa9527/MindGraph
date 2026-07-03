"""Add optional routing metadata to pinned conversations.

Revision ID: 0075
Revises: 0074
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0075"
down_revision: Union[str, None] = "0074"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("pinned_conversations"):
        return
    op.add_column("pinned_conversations", sa.Column("dify_user", sa.String(length=256), nullable=True))
    op.add_column("pinned_conversations", sa.Column("channel", sa.String(length=16), nullable=True))
    op.add_column("pinned_conversations", sa.Column("server", sa.Integer(), nullable=True))
    op.add_column("pinned_conversations", sa.Column("mindbot_config_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("pinned_conversations"):
        return
    op.drop_column("pinned_conversations", "mindbot_config_id")
    op.drop_column("pinned_conversations", "server")
    op.drop_column("pinned_conversations", "channel")
    op.drop_column("pinned_conversations", "dify_user")
