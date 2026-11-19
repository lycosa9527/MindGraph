"""Class-personalized learning sheet pages, one sequence number per student.

Revision ID: 0172
Revises: 0171
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from utils.db_rls.policy_builder import GLASSES_SHEET_EXPR

revision: str = "0172"
down_revision: Union[str, None] = "0171"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COPIES = "learning_sheet_copies"
_CAPTURES = "learning_sheet_captures"


def upgrade() -> None:
    """Create copy rows and remember which sequence a photo belongs to."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(_COPIES):
        op.create_table(
            _COPIES,
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("sheet_id", sa.String(length=36), nullable=False),
            sa.Column("seq", sa.Integer(), nullable=False),
            sa.Column("student_user_id", sa.Integer(), nullable=True),
            sa.Column("student_name", sa.String(length=80), nullable=False),
            sa.Column("class_name", sa.String(length=80), nullable=False),
            sa.Column("owner_user_id", sa.Integer(), nullable=False),
            sa.Column("organization_id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["sheet_id"], ["learning_sheet_tokens.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["student_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("sheet_id", "seq", name="uq_learning_sheet_copies_sheet_seq"),
        )
        op.create_index("ix_learning_sheet_copies_sheet_id", _COPIES, ["sheet_id"])
        op.create_index("ix_learning_sheet_copies_owner_user_id", _COPIES, ["owner_user_id"])
        op.create_index("ix_learning_sheet_copies_organization_id", _COPIES, ["organization_id"])
        op.execute(sa.text(f'ALTER TABLE "{_COPIES}" ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'ALTER TABLE "{_COPIES}" FORCE ROW LEVEL SECURITY'))
        op.execute(
            sa.text(
                f'CREATE POLICY "{_COPIES}_tenant" ON "{_COPIES}" '
                f"FOR ALL USING ({GLASSES_SHEET_EXPR}) "
                f"WITH CHECK ({GLASSES_SHEET_EXPR})"
            )
        )
    capture_columns = {column["name"] for column in inspector.get_columns(_CAPTURES)}
    if "copy_seq" not in capture_columns:
        op.add_column(_CAPTURES, sa.Column("copy_seq", sa.Integer(), nullable=True))


def downgrade() -> None:
    """Drop copy rows and the sequence stored on each photo."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table(_CAPTURES):
        capture_columns = {column["name"] for column in inspector.get_columns(_CAPTURES)}
        if "copy_seq" in capture_columns:
            op.drop_column(_CAPTURES, "copy_seq")
    if not inspector.has_table(_COPIES):
        return
    op.execute(sa.text(f'DROP POLICY IF EXISTS "{_COPIES}_tenant" ON "{_COPIES}"'))
    op.drop_index("ix_learning_sheet_copies_organization_id", table_name=_COPIES)
    op.drop_index("ix_learning_sheet_copies_owner_user_id", table_name=_COPIES)
    op.drop_index("ix_learning_sheet_copies_sheet_id", table_name=_COPIES)
    op.drop_table(_COPIES)
