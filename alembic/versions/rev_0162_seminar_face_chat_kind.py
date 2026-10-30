"""Mark seminar files that are face-to-face notes.

Revision ID: 0162
Revises: 0161
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0162"
down_revision: Union[str, None] = "0161"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "mindmate_seminar_background_files"


def upgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table(_TABLE):
        return
    cols = {col["name"] for col in sa.inspect(bind).get_columns(_TABLE)}
    if "kind" not in cols:
        op.add_column(
            _TABLE,
            sa.Column("kind", sa.String(length=32), nullable=False, server_default=""),
        )


def downgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table(_TABLE):
        return
    cols = {col["name"] for col in sa.inspect(bind).get_columns(_TABLE)}
    if "kind" in cols:
        op.drop_column(_TABLE, "kind")
