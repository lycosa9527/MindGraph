"""Add error_groups and error_events for admin error collection."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision: str = "0064"
down_revision: Union[str, None] = "0063"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if sa.inspect(bind).has_table("error_groups"):
        return

    op.create_table(
        "error_groups",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False, server_default="error"),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("component", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("exception_type", sa.String(length=256), nullable=False, server_default=""),
        sa.Column("sample_message", sa.Text(), nullable=False, server_default=""),
        sa.Column("occurrence_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("muted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_error_groups_fingerprint", "error_groups", ["fingerprint"], unique=True)
    op.create_index("ix_error_groups_last_seen", "error_groups", ["last_seen_at"])
    op.create_index("ix_error_groups_severity", "error_groups", ["severity"])
    op.create_index("ix_error_groups_source", "error_groups", ["source"])

    op.create_table(
        "error_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False, server_default="error"),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("component", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("exception_type", sa.String(length=256), nullable=False, server_default=""),
        sa.Column("message", sa.Text(), nullable=False, server_default=""),
        sa.Column("stacktrace", sa.Text(), nullable=True),
        sa.Column("tags", pg.JSONB(), nullable=True),
        sa.Column("request_id", sa.String(length=128), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("http_path", sa.String(length=512), nullable=True),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["group_id"], ["error_groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_error_events_created_at", "error_events", ["created_at"])
    op.create_index("ix_error_events_group_id", "error_events", ["group_id"])
    op.create_index("ix_error_events_severity", "error_events", ["severity"])
    op.create_index("ix_error_events_source", "error_events", ["source"])
    op.create_index("ix_error_events_fingerprint", "error_events", ["fingerprint"])


def downgrade() -> None:
    """Additive-only migration; downgrading risks dropping columns on legacy DBs."""
