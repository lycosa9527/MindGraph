"""Add mindmate_export_jobs for batched MindMate export."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision: str = "0062"
down_revision: Union[str, None] = "0061"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if sa.inspect(bind).has_table("mindmate_export_jobs"):
        return
    op.create_table(
        "mindmate_export_jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "running",
                "paused",
                "completed",
                "completed_with_gaps",
                "failed",
                "failed_verification",
                "cancelled",
                name="mindmate_export_job_status",
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("current_stage", sa.String(length=64), nullable=True),
        sa.Column("progress_percent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("progress_detail", pg.JSONB(), nullable=True),
        sa.Column("filters", pg.JSONB(), nullable=True),
        sa.Column("checkpoint", pg.JSONB(), nullable=True),
        sa.Column("verification_expected", pg.JSONB(), nullable=True),
        sa.Column("verification_report", pg.JSONB(), nullable=True),
        sa.Column("celery_task_id", sa.String(length=128), nullable=True),
        sa.Column("artifact_path", sa.String(length=512), nullable=True),
        sa.Column("artifact_format", sa.String(length=16), nullable=True),
        sa.Column("artifact_size_bytes", sa.Integer(), nullable=True),
        sa.Column("artifact_sha256", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_mindmate_export_jobs_created_by",
        "mindmate_export_jobs",
        ["created_by_user_id", "created_at"],
    )
    op.create_index(
        "ix_mindmate_export_jobs_status",
        "mindmate_export_jobs",
        ["status"],
    )


def downgrade() -> None:
    """Additive-only migration; downgrading risks dropping columns on legacy DBs."""
