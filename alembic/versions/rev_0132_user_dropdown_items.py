"""User avatar dropdown functions that can link a training course.

Revision ID: 0132
Revises: 0131
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0132"
down_revision: Union[str, None] = "0131"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "user_dropdown_items"
_ACCESS = "rls_is_system_mode()"


def _enable_rls() -> None:
    op.execute(sa.text(f'ALTER TABLE "{_TABLE}" ENABLE ROW LEVEL SECURITY'))
    op.execute(sa.text(f'ALTER TABLE "{_TABLE}" FORCE ROW LEVEL SECURITY'))
    op.execute(sa.text(f'CREATE POLICY "{_TABLE}_select" ON "{_TABLE}" FOR SELECT USING ({_ACCESS})'))
    op.execute(sa.text(f'CREATE POLICY "{_TABLE}_write" ON "{_TABLE}" FOR INSERT WITH CHECK ({_ACCESS})'))
    op.execute(
        sa.text(f'CREATE POLICY "{_TABLE}_update" ON "{_TABLE}" FOR UPDATE USING ({_ACCESS}) WITH CHECK ({_ACCESS})')
    )
    op.execute(sa.text(f'CREATE POLICY "{_TABLE}_delete" ON "{_TABLE}" FOR DELETE USING ({_ACCESS})'))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table(_TABLE):
        return
    op.create_table(
        _TABLE,
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("label", sa.String(length=40), nullable=False),
        sa.Column("course_id", sa.String(length=36), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["course_id"], ["training_courses.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_dropdown_items_course_id", _TABLE, ["course_id"])
    op.create_index("ix_user_dropdown_items_sort_order", _TABLE, ["sort_order"])
    _enable_rls()


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(_TABLE):
        return
    op.execute(sa.text(f'DROP POLICY IF EXISTS "{_TABLE}_select" ON "{_TABLE}"'))
    op.execute(sa.text(f'DROP POLICY IF EXISTS "{_TABLE}_write" ON "{_TABLE}"'))
    op.execute(sa.text(f'DROP POLICY IF EXISTS "{_TABLE}_update" ON "{_TABLE}"'))
    op.execute(sa.text(f'DROP POLICY IF EXISTS "{_TABLE}_delete" ON "{_TABLE}"'))
    op.drop_index("ix_user_dropdown_items_sort_order", table_name=_TABLE)
    op.drop_index("ix_user_dropdown_items_course_id", table_name=_TABLE)
    op.drop_table(_TABLE)
