"""Add optional diagram provenance columns.

Revision ID: 0074
Revises: 0073
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0074"
down_revision: Union[str, None] = "0073"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("diagrams"):
        return
    op.add_column("diagrams", sa.Column("source_channel", sa.String(length=32), nullable=True))
    op.add_column("diagrams", sa.Column("conversation_id", sa.String(length=128), nullable=True))
    op.add_column("diagrams", sa.Column("dify_user_key", sa.String(length=256), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("diagrams"):
        return
    op.drop_column("diagrams", "dify_user_key")
    op.drop_column("diagrams", "conversation_id")
    op.drop_column("diagrams", "source_channel")
