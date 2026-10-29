"""Separate seminar attendance from the closed invite list.

The host's history row must not lock a school seminar. ``invited`` marks a
seat on the closed roster. Public rooms and rooms that already named someone
besides the host stay closed.

Revision ID: 0160
Revises: 0159
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0160"
down_revision: Union[str, None] = "0159"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "mindmate_seminar_members"
_COLUMN = "invited"

_BACKFILL = sa.text(
    """
    UPDATE mindmate_seminar_members AS member
    SET invited = true
    FROM mindmate_seminar_sessions AS seminar
    WHERE seminar.id = member.session_id
      AND (
        seminar.visibility = 'network'
        OR EXISTS (
            SELECT 1
            FROM mindmate_seminar_members AS other
            WHERE other.session_id = member.session_id
              AND (
                other.user_id <> seminar.owner_user_id
                OR other.accepted IS FALSE
              )
        )
      )
    """
)


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
    op.execute(_BACKFILL)


def downgrade() -> None:
    bind = op.get_bind()
    if _COLUMN not in _column_names(bind):
        return
    op.drop_column(_TABLE, _COLUMN)
