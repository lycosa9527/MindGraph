"""Add kitty_one_sentence_sessions and session_id on turns."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0080"
down_revision: Union[str, None] = "0079"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("kitty_one_sentence_sessions"):
        op.create_table(
            "kitty_one_sentence_sessions",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("organization_id", sa.Integer(), nullable=True),
            sa.Column("diagram_scope", sa.String(length=36), nullable=False),
            sa.Column("diagram_id", sa.String(length=36), nullable=True),
            sa.Column("diagram_type", sa.String(length=50), nullable=True),
            sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
            sa.Column("turn_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("create_turn_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("edit_turn_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("first_prompt_preview", sa.String(length=120), nullable=True),
            sa.Column("last_voice_session_id", sa.String(length=32), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column(
                "last_activity_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.ForeignKeyConstraint(["diagram_id"], ["diagrams.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "user_id",
                "diagram_scope",
                name="uq_kitty_one_sentence_session_user_scope",
            ),
        )
        op.create_index(
            "ix_kitty_one_sentence_sessions_user_activity",
            "kitty_one_sentence_sessions",
            ["user_id", "last_activity_at"],
        )
        op.create_index(
            "ix_kitty_one_sentence_sessions_org_activity",
            "kitty_one_sentence_sessions",
            ["organization_id", "last_activity_at"],
        )
        op.create_index(
            op.f("ix_kitty_one_sentence_sessions_user_id"),
            "kitty_one_sentence_sessions",
            ["user_id"],
        )
        op.create_index(
            op.f("ix_kitty_one_sentence_sessions_diagram_scope"),
            "kitty_one_sentence_sessions",
            ["diagram_scope"],
        )

    if sa.inspect(bind).has_table("kitty_one_sentence_turns"):
        cols = {c["name"] for c in sa.inspect(bind).get_columns("kitty_one_sentence_turns")}
        if "session_id" not in cols:
            op.add_column(
                "kitty_one_sentence_turns",
                sa.Column("session_id", sa.String(length=36), nullable=True),
            )
            op.create_foreign_key(
                "fk_kitty_one_sentence_turns_session_id",
                "kitty_one_sentence_turns",
                "kitty_one_sentence_sessions",
                ["session_id"],
                ["id"],
                ondelete="CASCADE",
            )
            op.create_index(
                "ix_kitty_one_sentence_turns_session_created",
                "kitty_one_sentence_turns",
                ["session_id", "created_at"],
            )
            op.create_index(
                op.f("ix_kitty_one_sentence_turns_session_id"),
                "kitty_one_sentence_turns",
                ["session_id"],
            )


def downgrade() -> None:
    """Additive-only migration; downgrading risks dropping columns on legacy DBs."""
