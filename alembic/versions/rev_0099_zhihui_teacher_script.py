"""Add teacher_script on ZhiHui generation slides (classroom narration).

Revision ID: 0099
Revises: 0098
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0099"
down_revision: Union[str, None] = "0098"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_GEN = "zhihui_generations"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(_GEN):
        return
    columns = {col["name"] for col in inspector.get_columns(_GEN)}
    if "teacher_script" not in columns:
        op.add_column(
            _GEN,
            sa.Column("teacher_script", sa.Text(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(_GEN):
        return
    columns = {col["name"] for col in inspector.get_columns(_GEN)}
    if "teacher_script" in columns:
        op.drop_column(_GEN, "teacher_script")
