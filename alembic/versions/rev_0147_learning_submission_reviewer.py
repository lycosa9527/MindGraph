"""Record who graded a Learning Space submission.

Revision ID: 0147
Revises: 0146
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0147"
down_revision: Union[str, None] = "0146"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "learning_submissions"
_COLUMN = "reviewed_by"
_INDEX = "ix_learning_submissions_reviewed_by"
_FK = "fk_learning_submissions_reviewed_by_users"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(_TABLE):
        return
    cols = {column["name"] for column in inspector.get_columns(_TABLE)}
    if _COLUMN not in cols:
        op.add_column(_TABLE, sa.Column(_COLUMN, sa.Integer(), nullable=True))
    indexes = {index["name"] for index in inspector.get_indexes(_TABLE)}
    if _INDEX not in indexes:
        op.create_index(_INDEX, _TABLE, [_COLUMN])
    fks = {fk["name"] for fk in inspector.get_foreign_keys(_TABLE)}
    if _FK not in fks:
        op.create_foreign_key(_FK, _TABLE, "users", [_COLUMN], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(_TABLE):
        return
    fks = {fk["name"] for fk in inspector.get_foreign_keys(_TABLE)}
    if _FK in fks:
        op.drop_constraint(_FK, _TABLE, type_="foreignkey")
    indexes = {index["name"] for index in inspector.get_indexes(_TABLE)}
    if _INDEX in indexes:
        op.drop_index(_INDEX, table_name=_TABLE)
    cols = {column["name"] for column in inspector.get_columns(_TABLE)}
    if _COLUMN in cols:
        op.drop_column(_TABLE, _COLUMN)
