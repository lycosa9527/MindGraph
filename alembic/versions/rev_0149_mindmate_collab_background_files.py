"""Shared background files for a MindMate seminar.

Revision ID: 0149
Revises: 0148
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from utils.db_rls.policy_builder import (
    MINDMATE_COLLAB_LEGACY_FILE_CHECK as MINDMATE_COLLAB_FILE_CHECK,
    MINDMATE_COLLAB_LEGACY_FILE_EXPR as MINDMATE_COLLAB_FILE_EXPR,
    _create_all_policy,
)

revision: str = "0149"
down_revision: Union[str, None] = "0148"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "mindmate_collab_background_files"


def upgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table(_TABLE):
        op.create_table(
            _TABLE,
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("session_id", sa.String(length=36), nullable=False),
            sa.Column("uploader_user_id", sa.Integer(), nullable=False),
            sa.Column("filename", sa.String(length=180), nullable=False),
            sa.Column("content_type", sa.String(length=128), nullable=False),
            sa.Column("size_bytes", sa.Integer(), nullable=False),
            sa.Column("storage_key", sa.String(length=512), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["session_id"], ["mindmate_collab_sessions.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["uploader_user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_mindmate_collab_background_files_session_id", _TABLE, ["session_id"])
        op.create_index(
            "ix_mindmate_collab_background_files_session_created",
            _TABLE,
            ["session_id", "created_at"],
        )
        op.execute(sa.text(f'ALTER TABLE "{_TABLE}" ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'ALTER TABLE "{_TABLE}" FORCE ROW LEVEL SECURITY'))
        _create_all_policy(_TABLE, f"{_TABLE}_tenant", MINDMATE_COLLAB_FILE_EXPR, MINDMATE_COLLAB_FILE_CHECK)
    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mindgraph_app') THEN
                    GRANT SELECT, INSERT, UPDATE, DELETE
                    ON TABLE mindmate_collab_background_files TO mindgraph_app;
                END IF;
            END $$;
            """
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    if sa.inspect(bind).has_table(_TABLE):
        op.drop_table(_TABLE)
