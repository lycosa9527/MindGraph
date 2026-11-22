"""Local video file for clip lessons on a development machine.

Revision ID: 0174
Revises: 0173
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0174"
down_revision: Union[str, None] = "0173"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "clip_lessons"
_COLUMN = "local_video_key"


def upgrade() -> None:
    """Remember a development-machine video path on the lesson."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(_TABLE):
        return
    columns = {column["name"] for column in inspector.get_columns(_TABLE)}
    if _COLUMN in columns:
        return
    op.add_column(_TABLE, sa.Column(_COLUMN, sa.String(length=256), nullable=True))


def downgrade() -> None:
    """Drop the local video path."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(_TABLE):
        return
    columns = {column["name"] for column in inspector.get_columns(_TABLE)}
    if _COLUMN not in columns:
        return
    op.drop_column(_TABLE, _COLUMN)
