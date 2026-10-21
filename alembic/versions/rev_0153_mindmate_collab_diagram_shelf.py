"""Shelf a shared seminar diagram into resources or artifacts.

Revision ID: 0153
Revises: 0152
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0153"
down_revision: Union[str, None] = "0152"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "mindmate_collab_background_files"
_INDEX = "uq_mm_collab_bg_diagram"


def upgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table(_TABLE):
        return
    cols = {col["name"] for col in sa.inspect(bind).get_columns(_TABLE)}
    if "diagram_id" not in cols:
        op.add_column(_TABLE, sa.Column("diagram_id", sa.String(length=36), nullable=True))
    indexes = {idx["name"] for idx in sa.inspect(bind).get_indexes(_TABLE)}
    if _INDEX not in indexes:
        op.create_index(
            _INDEX,
            _TABLE,
            ["session_id", "diagram_id"],
            unique=True,
            postgresql_where=sa.text("diagram_id IS NOT NULL"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table(_TABLE):
        return
    indexes = {idx["name"] for idx in sa.inspect(bind).get_indexes(_TABLE)}
    if _INDEX in indexes:
        op.drop_index(_INDEX, table_name=_TABLE)
    cols = {col["name"] for col in sa.inspect(bind).get_columns(_TABLE)}
    if "diagram_id" in cols:
        op.drop_column(_TABLE, "diagram_id")
