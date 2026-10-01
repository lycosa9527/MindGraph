"""Owners can pin a saved MindMate seminar to the top of the library.

Revision ID: 0139
Revises: 0138
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0139"
down_revision: Union[str, None] = "0138"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "mindmate_collab_sessions"
_COLUMN = "library_pinned"


def _column_names(bind) -> set[str]:
    if not sa.inspect(bind).has_table(_TABLE):
        return set()
    return {column["name"] for column in sa.inspect(bind).get_columns(_TABLE)}


def upgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table(_TABLE):
        return
    if _COLUMN not in _column_names(bind):
        op.add_column(
            _TABLE,
            sa.Column(_COLUMN, sa.Boolean(), nullable=False, server_default=sa.false()),
        )


def downgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table(_TABLE):
        return
    if _COLUMN in _column_names(bind):
        op.drop_column(_TABLE, _COLUMN)
