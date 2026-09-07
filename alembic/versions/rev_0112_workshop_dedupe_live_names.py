"""Archive duplicate workshop channels; unique live (org, parent, name).

Revision ID: 0112
Revises: 0111
Create Date: 2026-09-07
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0112"
down_revision: Union[str, None] = "0111"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "chat_channels"
_INDEX = "uq_chat_channels_live_org_parent_name"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(_TABLE):
        return
    op.execute(
        sa.text(
            """
            WITH ranked AS (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY organization_id,
                                        COALESCE(parent_id, -1),
                                        name
                           ORDER BY id
                       ) AS rn
                FROM chat_channels
                WHERE NOT is_archived
                  AND channel_type <> 'announce'
            )
            UPDATE chat_channels AS channel
            SET is_archived = true
            FROM ranked
            WHERE channel.id = ranked.id
              AND ranked.rn > 1
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE chat_channels AS child
            SET is_archived = true
            FROM chat_channels AS parent
            WHERE child.parent_id = parent.id
              AND parent.is_archived
              AND NOT child.is_archived
            """
        )
    )
    existing = {idx["name"] for idx in inspector.get_indexes(_TABLE)}
    if _INDEX not in existing:
        op.execute(
            sa.text(
                f"""
                CREATE UNIQUE INDEX {_INDEX}
                ON {_TABLE} (organization_id, parent_id, name)
                NULLS NOT DISTINCT
                WHERE NOT is_archived AND channel_type <> 'announce'
                """
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(_TABLE):
        return
    existing = {idx["name"] for idx in inspector.get_indexes(_TABLE)}
    if _INDEX in existing:
        op.drop_index(_INDEX, table_name=_TABLE)
