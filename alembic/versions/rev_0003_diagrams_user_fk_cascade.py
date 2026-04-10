"""Fix diagrams.user_id FK to ON DELETE CASCADE.

Without this constraint the DB allows user rows to be deleted while
leaving diagram rows behind, producing orphaned records.

Baseline ``0001`` ``create_all`` may already create this FK with
``ON DELETE CASCADE`` (see ``Diagram.user_id``). Skip drop/recreate when
reflection shows CASCADE so the migration is a no-op on ORM-first installs.

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_FK_NAME = "diagrams_user_id_fkey"
_TABLE = "diagrams"
_COLUMN = "user_id"
_REF_TABLE = "users"
_REF_COLUMN = "id"


def _diagrams_user_fk_already_cascade(conn) -> bool:
    """True if the named FK exists and ON DELETE is CASCADE."""
    for fk in sa.inspect(conn).get_foreign_keys(_TABLE):
        if fk.get("name") != _FK_NAME:
            continue
        if fk.get("constrained_columns") != [_COLUMN]:
            continue
        opts = fk.get("options") or {}
        on_del = opts.get("ondelete")
        return str(on_del or "").upper() == "CASCADE"
    return False


def upgrade() -> None:
    bind = op.get_bind()
    if _diagrams_user_fk_already_cascade(bind):
        return

    with op.batch_alter_table(_TABLE) as batch_op:
        batch_op.drop_constraint(_FK_NAME, type_="foreignkey")
        batch_op.create_foreign_key(
            _FK_NAME,
            _REF_TABLE,
            [_COLUMN],
            [_REF_COLUMN],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    with op.batch_alter_table(_TABLE) as batch_op:
        batch_op.drop_constraint(_FK_NAME, type_="foreignkey")
        batch_op.create_foreign_key(
            _FK_NAME,
            _REF_TABLE,
            [_COLUMN],
            [_REF_COLUMN],
        )
