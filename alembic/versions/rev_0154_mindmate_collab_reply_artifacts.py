"""Seminar reply Word files archived as artifacts.

Revision ID: 0154
Revises: 0153
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0154"
down_revision: Union[str, None] = "0153"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "mindmate_collab_background_files"
_INDEX = "uq_mm_collab_bg_artifact_message"


def upgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table(_TABLE):
        return
    cols = {col["name"] for col in sa.inspect(bind).get_columns(_TABLE)}
    if "artifact" not in cols:
        op.add_column(
            _TABLE,
            sa.Column("artifact", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
    if "source_message_id" not in cols:
        op.add_column(_TABLE, sa.Column("source_message_id", sa.Integer(), nullable=True))
    indexes = {idx["name"] for idx in sa.inspect(bind).get_indexes(_TABLE)}
    if _INDEX not in indexes:
        op.create_index(_INDEX, _TABLE, ["session_id", "source_message_id"], unique=True)


def downgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table(_TABLE):
        return
    indexes = {idx["name"] for idx in sa.inspect(bind).get_indexes(_TABLE)}
    if _INDEX in indexes:
        op.drop_index(_INDEX, table_name=_TABLE)
    cols = {col["name"] for col in sa.inspect(bind).get_columns(_TABLE)}
    if "source_message_id" in cols:
        op.drop_column(_TABLE, "source_message_id")
    if "artifact" in cols:
        op.drop_column(_TABLE, "artifact")
