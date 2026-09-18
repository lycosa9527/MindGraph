"""Add teacher review fields to learning_submissions.

Revision ID: 0123
Revises: 0122
Create Date: 2026-09-17
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0123"
down_revision: Union[str, None] = "0122"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("learning_submissions"):
        return
    cols = {c["name"] for c in inspector.get_columns("learning_submissions")}
    if "review_scores" not in cols:
        op.add_column(
            "learning_submissions",
            sa.Column("review_scores", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        )
    if "review_comment" not in cols:
        op.add_column(
            "learning_submissions",
            sa.Column("review_comment", sa.Text(), nullable=True),
        )
    if "review_liked" not in cols:
        op.add_column(
            "learning_submissions",
            sa.Column(
                "review_liked",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )
    if "review_pinned" not in cols:
        op.add_column(
            "learning_submissions",
            sa.Column(
                "review_pinned",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )
    if "reviewed_at" not in cols:
        op.add_column(
            "learning_submissions",
            sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("learning_submissions"):
        return
    cols = {c["name"] for c in inspector.get_columns("learning_submissions")}
    for name in (
        "reviewed_at",
        "review_pinned",
        "review_liked",
        "review_comment",
        "review_scores",
    ):
        if name in cols:
            op.drop_column("learning_submissions", name)
