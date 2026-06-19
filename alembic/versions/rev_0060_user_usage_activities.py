"""Add user_usage_activities for admin user activity timeline."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0060"
down_revision: Union[str, None] = "0059"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if sa.inspect(bind).has_table("user_usage_activities"):
        return
    op.create_table(
        "user_usage_activities",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("prompt_preview", sa.String(length=120), nullable=True),
        sa.Column("reply_preview", sa.String(length=120), nullable=True),
        sa.Column("diagram_type", sa.String(length=50), nullable=True),
        sa.Column("diagram_id", sa.String(length=36), nullable=True),
        sa.Column("conversation_id", sa.String(length=128), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["diagram_id"], ["diagrams.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_user_usage_activities_user_id_desc",
        "user_usage_activities",
        ["user_id", "id"],
    )
    op.create_index(
        "ix_user_usage_activities_user_created",
        "user_usage_activities",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    """Additive-only migration; downgrading risks dropping columns on legacy DBs."""
