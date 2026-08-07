"""Unique (conversation_id, slide_index) for ZhiHui deck slides.

Revision ID: 0100
Revises: 0099
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0100"
down_revision: Union[str, None] = "0099"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_GEN = "zhihui_generations"
_INDEX = "uq_zhihui_generations_conversation_slide"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(_GEN):
        return
    # Keep the earliest row when duplicate slide indexes exist.
    op.execute(
        sa.text(
            f"""
            DELETE FROM {_GEN} AS dup
            USING {_GEN} AS keep
            WHERE dup.conversation_id IS NOT NULL
              AND dup.slide_index IS NOT NULL
              AND dup.conversation_id = keep.conversation_id
              AND dup.slide_index = keep.slide_index
              AND (
                dup.created_at > keep.created_at
                OR (dup.created_at = keep.created_at AND dup.id > keep.id)
              )
            """
        )
    )
    existing = {idx["name"] for idx in inspector.get_indexes(_GEN)}
    if _INDEX not in existing:
        op.create_index(
            _INDEX,
            _GEN,
            ["conversation_id", "slide_index"],
            unique=True,
            postgresql_where=sa.text("conversation_id IS NOT NULL AND slide_index IS NOT NULL"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(_GEN):
        return
    existing = {idx["name"] for idx in inspector.get_indexes(_GEN)}
    if _INDEX in existing:
        op.drop_index(_INDEX, table_name=_GEN)
