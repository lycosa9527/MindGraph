"""Mind Classroom lecture jobs and slides with owner RLS.

Revision ID: 0103
Revises: 0102
Create Date: 2026-08-16
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0103"
down_revision: Union[str, None] = "0102"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_JOBS = "mind_classroom_jobs"
_SLIDES = "mind_classroom_slides"
_ACCESS = "user_id = rls_current_user_id() OR rls_is_system_mode()"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(_JOBS):
        op.create_table(
            _JOBS,
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("organization_id", sa.Integer(), nullable=True),
            sa.Column("diagram_id", sa.String(length=36), nullable=True),
            sa.Column("spec_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column("settings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column("spec_hash", sa.String(length=64), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
            sa.Column("current_stage", sa.String(length=32), nullable=True),
            sa.Column("progress", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("result_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("lesson_plan_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("celery_task_id", sa.String(length=64), nullable=True),
            sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("attempts", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("started_at", sa.DateTime(), nullable=True),
            sa.Column("finished_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_mind_classroom_jobs_id", _JOBS, ["id"])
        op.create_index("ix_mind_classroom_jobs_user_id", _JOBS, ["user_id"])
        op.create_index("ix_mind_classroom_jobs_organization_id", _JOBS, ["organization_id"])
        op.create_index("ix_mind_classroom_jobs_diagram_id", _JOBS, ["diagram_id"])
        op.create_index("ix_mind_classroom_jobs_spec_hash", _JOBS, ["spec_hash"])
        op.create_index("ix_mind_classroom_jobs_status", _JOBS, ["status"])
        op.create_index("ix_mind_classroom_jobs_created_at", _JOBS, ["created_at"])
        op.create_index("ix_mind_classroom_jobs_updated_at", _JOBS, ["updated_at"])
        op.create_index("ix_mind_classroom_jobs_user_status", _JOBS, ["user_id", "status"])
        op.create_index("ix_mind_classroom_jobs_reuse", _JOBS, ["user_id", "spec_hash"])
        op.execute(sa.text(f'ALTER TABLE "{_JOBS}" ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'ALTER TABLE "{_JOBS}" FORCE ROW LEVEL SECURITY'))
        op.execute(
            sa.text(f'CREATE POLICY "{_JOBS}_access" ON "{_JOBS}" FOR ALL USING ({_ACCESS}) WITH CHECK ({_ACCESS})')
        )

    if not inspector.has_table(_SLIDES):
        op.create_table(
            _SLIDES,
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column(
                "job_id",
                sa.String(length=36),
                sa.ForeignKey("mind_classroom_jobs.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("slide_index", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(length=256), nullable=True),
            sa.Column("teacher_script", sa.Text(), nullable=True),
            sa.Column("focus_node_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("cos_logical_key", sa.String(length=512), nullable=False),
            sa.Column("content_type", sa.String(length=64), nullable=False, server_default="image/png"),
            sa.Column("size", sa.String(length=32), nullable=True),
            sa.Column("prompt", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_mind_classroom_slides_id", _SLIDES, ["id"])
        op.create_index("ix_mind_classroom_slides_job_id", _SLIDES, ["job_id"])
        op.create_index("ix_mind_classroom_slides_user_id", _SLIDES, ["user_id"])
        op.create_index("ix_mind_classroom_slides_job_index", _SLIDES, ["job_id", "slide_index"], unique=True)
        op.execute(sa.text(f'ALTER TABLE "{_SLIDES}" ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'ALTER TABLE "{_SLIDES}" FORCE ROW LEVEL SECURITY'))
        op.execute(
            sa.text(f'CREATE POLICY "{_SLIDES}_access" ON "{_SLIDES}" FOR ALL USING ({_ACCESS}) WITH CHECK ({_ACCESS})')
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table(_SLIDES):
        op.execute(sa.text(f'DROP POLICY IF EXISTS "{_SLIDES}_access" ON "{_SLIDES}"'))
        op.drop_table(_SLIDES)
    if inspector.has_table(_JOBS):
        op.execute(sa.text(f'DROP POLICY IF EXISTS "{_JOBS}_access" ON "{_JOBS}"'))
        op.drop_table(_JOBS)
