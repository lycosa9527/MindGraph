"""Add kitty_one_sentence_turns for durable one-sentence panel chat history."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0078"
down_revision: Union[str, None] = "0077"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if sa.inspect(bind).has_table("kitty_one_sentence_turns"):
        return
    op.create_table(
        "kitty_one_sentence_turns",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("scope", sa.String(length=36), nullable=False),
        sa.Column("turn_id", sa.String(length=64), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("phase", sa.String(length=16), nullable=False, server_default="edit"),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="unknown"),
        sa.Column("action", sa.String(length=64), nullable=True),
        sa.Column("outcome", sa.String(length=32), nullable=True),
        sa.Column("user_text", sa.Text(), nullable=True),
        sa.Column("diagram_type", sa.String(length=50), nullable=True),
        sa.Column("voice_session_id", sa.String(length=32), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scope", "turn_id", name="uq_kitty_one_sentence_turn_scope_turn"),
    )
    op.create_index(
        "ix_kitty_one_sentence_turns_scope_created",
        "kitty_one_sentence_turns",
        ["scope", "created_at"],
    )
    op.create_index(
        "ix_kitty_one_sentence_turns_user_created",
        "kitty_one_sentence_turns",
        ["user_id", "created_at"],
    )
    op.create_index(
        op.f("ix_kitty_one_sentence_turns_user_id"),
        "kitty_one_sentence_turns",
        ["user_id"],
    )
    op.create_index(
        op.f("ix_kitty_one_sentence_turns_scope"),
        "kitty_one_sentence_turns",
        ["scope"],
    )


def downgrade() -> None:
    """Additive-only migration; downgrading risks dropping columns on legacy DBs."""
