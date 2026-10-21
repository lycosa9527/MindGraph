"""Pin flag for MindMate seminar background files.

Revision ID: 0149
Revises: 0148
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0149"
down_revision: Union[str, None] = "0148"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "mindmate_collab_background_files"


def upgrade() -> None:
    bind = op.get_bind()
    cols = {col["name"] for col in sa.inspect(bind).get_columns(_TABLE)}
    if "pinned" not in cols:
        op.add_column(
            _TABLE,
            sa.Column("pinned", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
    if "pinned_at" not in cols:
        op.add_column(
            _TABLE,
            sa.Column("pinned_at", sa.DateTime(timezone=True), nullable=True),
        )
    indexes = {idx["name"] for idx in sa.inspect(bind).get_indexes(_TABLE)}
    if "ix_mindmate_collab_background_files_session_pinned" not in indexes:
        op.create_index(
            "ix_mindmate_collab_background_files_session_pinned",
            _TABLE,
            ["session_id", "pinned", "pinned_at"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    indexes = {idx["name"] for idx in sa.inspect(bind).get_indexes(_TABLE)}
    if "ix_mindmate_collab_background_files_session_pinned" in indexes:
        op.drop_index("ix_mindmate_collab_background_files_session_pinned", table_name=_TABLE)
    cols = {col["name"] for col in sa.inspect(bind).get_columns(_TABLE)}
    if "pinned_at" in cols:
        op.drop_column(_TABLE, "pinned_at")
    if "pinned" in cols:
        op.drop_column(_TABLE, "pinned")
