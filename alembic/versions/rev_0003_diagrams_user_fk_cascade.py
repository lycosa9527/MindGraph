"""Fix diagrams.user_id FK to ON DELETE CASCADE.

Without this constraint the DB allows user rows to be deleted while
leaving diagram rows behind, producing orphaned records.

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-02
"""

from typing import Sequence, Union

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


def upgrade() -> None:
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
