"""Owner can keep a finished MindMate seminar in their library.

Revision ID: 0133
Revises: 0132
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0133"
down_revision: Union[str, None] = "0132"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "mindmate_collab_sessions"
_COLUMN = "library_saved_at"
_INDEX = "ix_mindmate_collab_sessions_owner_library"


def _column_names(bind) -> set[str]:
    if not sa.inspect(bind).has_table(_TABLE):
        return set()
    return {column["name"] for column in sa.inspect(bind).get_columns(_TABLE)}


def _index_names(bind) -> set[str]:
    if not sa.inspect(bind).has_table(_TABLE):
        return set()
    names: set[str] = set()
    for index in sa.inspect(bind).get_indexes(_TABLE):
        name = index["name"]
        if isinstance(name, str):
            names.add(name)
    return names


def upgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table(_TABLE):
        return
    if _COLUMN not in _column_names(bind):
        op.add_column(_TABLE, sa.Column(_COLUMN, sa.DateTime(timezone=True), nullable=True))
    if _INDEX not in _index_names(bind):
        op.create_index(_INDEX, _TABLE, ["owner_user_id", _COLUMN])


def downgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table(_TABLE):
        return
    if _INDEX in _index_names(bind):
        op.drop_index(_INDEX, table_name=_TABLE)
    if _COLUMN in _column_names(bind):
        op.drop_column(_TABLE, _COLUMN)
