"""Shared group highlights for a MindMate seminar.

Revision ID: 0176
Revises: 0175
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from utils.db_rls.policy_builder import (
    MINDMATE_COLLAB_HIGHLIGHT_CHECK,
    MINDMATE_COLLAB_HIGHLIGHT_EXPR,
    _create_all_policy,
)

revision: str = "0176"
down_revision: Union[str, None] = "0175"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "mindmate_seminar_highlights"


def upgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table(_TABLE):
        op.create_table(
            _TABLE,
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("session_id", sa.String(length=36), nullable=False),
            sa.Column("created_by_user_id", sa.Integer(), nullable=False),
            sa.Column("created_by_name", sa.String(length=80), nullable=False),
            sa.Column("author_name", sa.String(length=80), nullable=False),
            sa.Column("text", sa.Text(), nullable=False),
            sa.Column("message_id", sa.Integer(), nullable=True),
            sa.Column("message_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["session_id"], ["mindmate_seminar_sessions.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_mindmate_seminar_highlights_session_id", _TABLE, ["session_id"])
        op.create_index(
            "ix_mindmate_seminar_highlights_session_created",
            _TABLE,
            ["session_id", "created_at"],
        )
        op.create_index(
            "uq_mm_seminar_highlight_message_creator",
            _TABLE,
            ["session_id", "message_id", "created_by_user_id"],
            unique=True,
            postgresql_where=sa.text("message_id IS NOT NULL"),
        )
        op.execute(sa.text(f'ALTER TABLE "{_TABLE}" ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'ALTER TABLE "{_TABLE}" FORCE ROW LEVEL SECURITY'))
        _create_all_policy(
            _TABLE,
            f"{_TABLE}_tenant",
            MINDMATE_COLLAB_HIGHLIGHT_EXPR,
            MINDMATE_COLLAB_HIGHLIGHT_CHECK,
        )
    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mindgraph_app') THEN
                    GRANT SELECT, INSERT, UPDATE, DELETE
                    ON TABLE mindmate_seminar_highlights TO mindgraph_app;
                END IF;
            END $$;
            """
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    if sa.inspect(bind).has_table(_TABLE):
        op.drop_table(_TABLE)
