"""Add mindmate_collab_sessions and mindmate_collab_messages tables."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0076"
down_revision: Union[str, None] = "0075"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if sa.inspect(bind).has_table("mindmate_collab_sessions"):
        return
    op.create_table(
        "mindmate_collab_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False, server_default="MindMate Collab"),
        sa.Column("dify_conversation_id", sa.String(length=128), nullable=True),
        sa.Column("visibility", sa.String(length=32), nullable=False, server_default="organization"),
        sa.Column("duration_preset", sa.String(length=16), nullable=False, server_default="today"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_mindmate_collab_sessions_code"),
    )
    op.create_index(
        "ix_mindmate_collab_sessions_org",
        "mindmate_collab_sessions",
        ["organization_id"],
    )
    op.create_index(
        "ix_mindmate_collab_sessions_owner",
        "mindmate_collab_sessions",
        ["owner_user_id"],
    )
    op.create_index(
        "ix_mindmate_collab_sessions_active_org",
        "mindmate_collab_sessions",
        ["organization_id", "visibility"],
        postgresql_where=sa.text("ended_at IS NULL"),
    )
    op.create_table(
        "mindmate_collab_messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("sender_user_id", sa.Integer(), nullable=True),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["session_id"], ["mindmate_collab_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sender_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_mindmate_collab_messages_session_created",
        "mindmate_collab_messages",
        ["session_id", "created_at"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("mindmate_collab_messages"):
        return
    op.drop_index("ix_mindmate_collab_messages_session_created", table_name="mindmate_collab_messages")
    op.drop_table("mindmate_collab_messages")
    op.drop_index("ix_mindmate_collab_sessions_active_org", table_name="mindmate_collab_sessions")
    op.drop_index("ix_mindmate_collab_sessions_owner", table_name="mindmate_collab_sessions")
    op.drop_index("ix_mindmate_collab_sessions_org", table_name="mindmate_collab_sessions")
    op.drop_table("mindmate_collab_sessions")
