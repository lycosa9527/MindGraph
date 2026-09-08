"""Keep a single live workshop announce channel.

Revision ID: 0110
Revises: 0109
Create Date: 2026-09-07
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0110"
down_revision: Union[str, None] = "0109"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "chat_channels"
_INDEX = "uq_chat_channels_single_announce"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(_TABLE):
        return
    op.execute(
        sa.text(
            """
            UPDATE chat_channels
            SET is_archived = true
            WHERE id IN (
                SELECT id FROM chat_channels
                WHERE channel_type = 'announce'
                  AND NOT is_archived
                  AND id <> (
                      SELECT MIN(id) FROM chat_channels
                      WHERE channel_type = 'announce' AND NOT is_archived
                  )
            )
            """
        )
    )
    existing = {idx["name"] for idx in inspector.get_indexes(_TABLE)}
    if _INDEX not in existing:
        op.create_index(
            _INDEX,
            _TABLE,
            ["channel_type"],
            unique=True,
            postgresql_where=sa.text("channel_type = 'announce' AND NOT is_archived"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(_TABLE):
        return
    existing = {idx["name"] for idx in inspector.get_indexes(_TABLE)}
    if _INDEX in existing:
        op.drop_index(_INDEX, table_name=_TABLE)
