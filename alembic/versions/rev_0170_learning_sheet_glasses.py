"""Printed learning-sheet QR tokens and glasses photo captures.

Revision ID: 0170
Revises: 0169
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from utils.db_rls.policy_builder import GLASSES_SHEET_EXPR

revision: str = "0170"
down_revision: Union[str, None] = "0169"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TOKENS = "learning_sheet_tokens"
_CAPTURES = "learning_sheet_captures"


def _enable_tenant(table: str) -> None:
    op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
    op.execute(sa.text(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY'))
    op.execute(
        sa.text(
            f'CREATE POLICY "{table}_tenant" ON "{table}" '
            f"FOR ALL USING ({GLASSES_SHEET_EXPR}) "
            f"WITH CHECK ({GLASSES_SHEET_EXPR})"
        )
    )


def upgrade() -> None:
    """Create the sheet token and capture tables."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(_TOKENS):
        op.create_table(
            _TOKENS,
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("owner_user_id", sa.Integer(), nullable=False),
            sa.Column("organization_id", sa.Integer(), nullable=False),
            sa.Column("diagram_id", sa.String(length=36), nullable=True),
            sa.Column("course_spec", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_learning_sheet_tokens_owner_user_id", _TOKENS, ["owner_user_id"])
        op.create_index("ix_learning_sheet_tokens_organization_id", _TOKENS, ["organization_id"])
        op.create_index("ix_learning_sheet_tokens_diagram_id", _TOKENS, ["diagram_id"])
        _enable_tenant(_TOKENS)
    if not inspector.has_table(_CAPTURES):
        op.create_table(
            _CAPTURES,
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("sheet_id", sa.String(length=36), nullable=False),
            sa.Column("owner_user_id", sa.Integer(), nullable=False),
            sa.Column("organization_id", sa.Integer(), nullable=False),
            sa.Column("image_ref", sa.String(length=240), nullable=False),
            sa.Column("student_name", sa.String(length=80), nullable=False, server_default=""),
            sa.Column("class_name", sa.String(length=80), nullable=False, server_default=""),
            sa.Column("ocr_spec", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("ocr_error", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["sheet_id"], [f"{_TOKENS}.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_learning_sheet_captures_sheet_id", _CAPTURES, ["sheet_id"])
        op.create_index("ix_learning_sheet_captures_organization_id", _CAPTURES, ["organization_id"])
        op.create_index(
            "ix_learning_sheet_captures_owner_created",
            _CAPTURES,
            ["owner_user_id", "created_at"],
        )
        _enable_tenant(_CAPTURES)


def downgrade() -> None:
    """Drop the glasses sheet tables."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table(_CAPTURES):
        op.execute(sa.text(f'DROP POLICY IF EXISTS "{_CAPTURES}_tenant" ON "{_CAPTURES}"'))
        op.drop_index("ix_learning_sheet_captures_owner_created", table_name=_CAPTURES)
        op.drop_index("ix_learning_sheet_captures_organization_id", table_name=_CAPTURES)
        op.drop_index("ix_learning_sheet_captures_sheet_id", table_name=_CAPTURES)
        op.drop_table(_CAPTURES)
    if inspector.has_table(_TOKENS):
        op.execute(sa.text(f'DROP POLICY IF EXISTS "{_TOKENS}_tenant" ON "{_TOKENS}"'))
        op.drop_index("ix_learning_sheet_tokens_diagram_id", table_name=_TOKENS)
        op.drop_index("ix_learning_sheet_tokens_organization_id", table_name=_TOKENS)
        op.drop_index("ix_learning_sheet_tokens_owner_user_id", table_name=_TOKENS)
        op.drop_table(_TOKENS)
