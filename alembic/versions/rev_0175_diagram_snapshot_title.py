"""Add optional display title to diagram_snapshots.

Revision ID: 0175
Revises: 0174
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0175"
down_revision: Union[str, None] = "0174"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "diagram_snapshots"
_COLUMN = "title"


def upgrade() -> None:
    """Allow users to rename a snapshot without changing its version number."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(_TABLE):
        return
    columns = {col["name"] for col in inspector.get_columns(_TABLE)}
    if _COLUMN in columns:
        return
    op.add_column(
        _TABLE,
        sa.Column(_COLUMN, sa.String(length=100), nullable=True),
    )


def downgrade() -> None:
    """Drop the optional snapshot title column."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(_TABLE):
        return
    columns = {col["name"] for col in inspector.get_columns(_TABLE)}
    if _COLUMN not in columns:
        return
    op.drop_column(_TABLE, _COLUMN)
