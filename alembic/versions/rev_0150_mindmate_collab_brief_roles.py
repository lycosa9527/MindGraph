"""Seminar brief fields and member roles for MindMate collab.

Revision ID: 0150
Revises: 0149
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0150"
down_revision: Union[str, None] = "0149"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    session_cols = {col["name"] for col in inspector.get_columns("mindmate_collab_sessions")}
    if "brief_topic" not in session_cols:
        op.add_column(
            "mindmate_collab_sessions",
            sa.Column("brief_topic", sa.String(length=200), nullable=True),
        )
    if "brief_goals" not in session_cols:
        op.add_column(
            "mindmate_collab_sessions",
            sa.Column("brief_goals", sa.Text(), nullable=True),
        )

    member_cols = {col["name"] for col in inspector.get_columns("mindmate_collab_members")}
    if "seminar_role" not in member_cols:
        op.add_column(
            "mindmate_collab_members",
            sa.Column(
                "seminar_role",
                sa.String(length=32),
                nullable=False,
                server_default="observer",
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    member_cols = {col["name"] for col in inspector.get_columns("mindmate_collab_members")}
    if "seminar_role" in member_cols:
        op.drop_column("mindmate_collab_members", "seminar_role")
    session_cols = {col["name"] for col in inspector.get_columns("mindmate_collab_sessions")}
    if "brief_goals" in session_cols:
        op.drop_column("mindmate_collab_sessions", "brief_goals")
    if "brief_topic" in session_cols:
        op.drop_column("mindmate_collab_sessions", "brief_topic")
