"""Create Mate Learning tables (problems, sessions, stages, artifacts).

Revision ID: 0089
Revises: 0088
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision: str = "0089"
down_revision: Union[str, None] = "0088"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_JSONB = sa.text("'[]'::jsonb")
_JSONB_OBJ = sa.text("'{}'::jsonb")


def _create_maite_problems() -> None:
    op.create_table(
        "maite_problems",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("clean_text", sa.Text(), nullable=False),
        sa.Column("image_url", sa.String(length=512), nullable=True),
        sa.Column("subject", sa.String(length=64), nullable=False, server_default="高中数学"),
        sa.Column("grade_level", sa.String(length=64), nullable=True),
        sa.Column("topic_tags", pg.JSONB(), nullable=False, server_default=_JSONB),
        sa.Column("difficulty", sa.String(length=32), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_maite_problems_user_id"), "maite_problems", ["user_id"])
    op.create_index(op.f("ix_maite_problems_organization_id"), "maite_problems", ["organization_id"])


def _create_maite_inquiry_sessions() -> None:
    op.create_table(
        "maite_inquiry_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("problem_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="created"),
        sa.Column("current_stage", sa.String(length=32), nullable=False, server_default="created"),
        sa.Column("original_session_id", sa.Integer(), nullable=True),
        sa.Column("version_no", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("redo_reason", sa.Text(), nullable=True),
        sa.Column("mode", sa.String(length=16), nullable=False, server_default="inquiry"),
        sa.Column("title", sa.String(length=200), nullable=True),
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
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["problem_id"], ["maite_problems.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_maite_inquiry_sessions_user_id"), "maite_inquiry_sessions", ["user_id"])
    op.create_index(op.f("ix_maite_inquiry_sessions_organization_id"), "maite_inquiry_sessions", ["organization_id"])
    op.create_index(op.f("ix_maite_inquiry_sessions_problem_id"), "maite_inquiry_sessions", ["problem_id"])
    op.create_index(op.f("ix_maite_inquiry_sessions_status"), "maite_inquiry_sessions", ["status"])
    op.create_index(op.f("ix_maite_inquiry_sessions_mode"), "maite_inquiry_sessions", ["mode"])
    op.create_index(
        op.f("ix_maite_inquiry_sessions_original_session_id"),
        "maite_inquiry_sessions",
        ["original_session_id"],
    )


def _create_stage_tables() -> None:
    op.create_table(
        "maite_problem_analyses",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("problem_id", sa.Integer(), nullable=False),
        sa.Column("knowledge_points", pg.JSONB(), nullable=False, server_default=_JSONB),
        sa.Column("methods", pg.JSONB(), nullable=False, server_default=_JSONB),
        sa.Column("problem_type", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("difficulty", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("core_goal", sa.Text(), nullable=False, server_default=""),
        sa.Column("possible_block_risks", pg.JSONB(), nullable=False, server_default=_JSONB),
        sa.Column("geometry_required", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("mvp_recommended", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("mvp_notice", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["problem_id"], ["maite_problems.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_maite_problem_analyses_problem_id"), "maite_problem_analyses", ["problem_id"])

    op.create_table(
        "maite_self_assessments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("items", pg.JSONB(), nullable=False, server_default=_JSONB),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["session_id"], ["maite_inquiry_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_maite_self_assessments_session_id"), "maite_self_assessments", ["session_id"])

    op.create_table(
        "maite_decompose_submissions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("condition_table", pg.JSONB(), nullable=False, server_default=_JSONB),
        sa.Column("step_table", pg.JSONB(), nullable=False, server_default=_JSONB),
        sa.Column("model_table", pg.JSONB(), nullable=False, server_default=_JSONB),
        sa.Column("validation_warnings", pg.JSONB(), nullable=False, server_default=_JSONB),
        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["session_id"], ["maite_inquiry_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_maite_decompose_submissions_session_id"),
        "maite_decompose_submissions",
        ["session_id"],
    )

    op.create_table(
        "maite_diagnosis_results",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("decompose_submission_id", sa.Integer(), nullable=True),
        sa.Column("stage_results", pg.JSONB(), nullable=False, server_default=_JSONB),
        sa.Column("final_block_report", pg.JSONB(), nullable=False, server_default=_JSONB),
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
        sa.ForeignKeyConstraint(["session_id"], ["maite_inquiry_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_maite_diagnosis_results_session_id"), "maite_diagnosis_results", ["session_id"])
    op.create_index(
        op.f("ix_maite_diagnosis_results_decompose_submission_id"),
        "maite_diagnosis_results",
        ["decompose_submission_id"],
    )

    op.create_table(
        "maite_remedy_tasks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("diagnosis_result_id", sa.Integer(), nullable=False),
        sa.Column("block_type", sa.String(length=64), nullable=False),
        sa.Column("block_name", sa.String(length=200), nullable=False),
        sa.Column("source_block", pg.JSONB(), nullable=False, server_default=_JSONB_OBJ),
        sa.Column("task_payload", pg.JSONB(), nullable=False, server_default=_JSONB_OBJ),
        sa.Column("student_response", sa.Text(), nullable=True),
        sa.Column("student_confidence", sa.String(length=32), nullable=True),
        sa.Column("ai_feedback", pg.JSONB(), nullable=False, server_default=_JSONB_OBJ),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
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
        sa.ForeignKeyConstraint(["session_id"], ["maite_inquiry_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_maite_remedy_tasks_session_id"), "maite_remedy_tasks", ["session_id"])
    op.create_index(op.f("ix_maite_remedy_tasks_diagnosis_result_id"), "maite_remedy_tasks", ["diagnosis_result_id"])
    op.create_index(op.f("ix_maite_remedy_tasks_block_type"), "maite_remedy_tasks", ["block_type"])
    op.create_index(op.f("ix_maite_remedy_tasks_status"), "maite_remedy_tasks", ["status"])

    op.create_table(
        "maite_variant_tasks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("variant_type", sa.String(length=32), nullable=False),
        sa.Column("variant_text", sa.Text(), nullable=False),
        sa.Column("changed_part", sa.Text(), nullable=False, server_default=""),
        sa.Column("expected_strategy", sa.Text(), nullable=False, server_default=""),
        sa.Column("student_answer", sa.Text(), nullable=True),
        sa.Column("student_strategy", sa.Text(), nullable=True),
        sa.Column("ai_feedback", pg.JSONB(), nullable=False, server_default=_JSONB_OBJ),
        sa.Column("transfer_result", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
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
        sa.ForeignKeyConstraint(["session_id"], ["maite_inquiry_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_maite_variant_tasks_session_id"), "maite_variant_tasks", ["session_id"])
    op.create_index(op.f("ix_maite_variant_tasks_variant_type"), "maite_variant_tasks", ["variant_type"])
    op.create_index(op.f("ix_maite_variant_tasks_status"), "maite_variant_tasks", ["status"])


def _create_artifact_tables() -> None:
    op.create_table(
        "maite_session_reports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("report_markdown", sa.Text(), nullable=False),
        sa.Column("sections", pg.JSONB(), nullable=False, server_default=_JSONB_OBJ),
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
        sa.ForeignKeyConstraint(["session_id"], ["maite_inquiry_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_maite_session_reports_session_id"), "maite_session_reports", ["session_id"])

    op.create_table(
        "maite_graph_node_progress",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("graph_type", sa.String(length=32), nullable=False),
        sa.Column("node_name", sa.String(length=200), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=False, server_default=""),
        sa.Column("source", sa.String(length=64), nullable=False, server_default=""),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["session_id"], ["maite_inquiry_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_maite_graph_node_progress_user_id"), "maite_graph_node_progress", ["user_id"])
    op.create_index(op.f("ix_maite_graph_node_progress_session_id"), "maite_graph_node_progress", ["session_id"])
    op.create_index(op.f("ix_maite_graph_node_progress_graph_type"), "maite_graph_node_progress", ["graph_type"])
    op.create_index(op.f("ix_maite_graph_node_progress_node_name"), "maite_graph_node_progress", ["node_name"])
    op.create_index(op.f("ix_maite_graph_node_progress_state"), "maite_graph_node_progress", ["state"])

    op.create_table(
        "maite_prompt_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("session_id", sa.Integer(), nullable=True),
        sa.Column("prompt_id", sa.String(length=64), nullable=False),
        sa.Column("prompt_version", sa.String(length=32), nullable=False),
        sa.Column("model_name", sa.String(length=128), nullable=False),
        sa.Column("task_type", sa.String(length=64), nullable=False),
        sa.Column("input_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("raw_output", sa.Text(), nullable=False, server_default=""),
        sa.Column("validated_output", pg.JSONB(), nullable=False, server_default=_JSONB_OBJ),
        sa.Column("schema_name", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("validation_status", sa.String(length=32), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_maite_prompt_runs_user_id"), "maite_prompt_runs", ["user_id"])
    op.create_index(op.f("ix_maite_prompt_runs_session_id"), "maite_prompt_runs", ["session_id"])
    op.create_index(op.f("ix_maite_prompt_runs_prompt_id"), "maite_prompt_runs", ["prompt_id"])
    op.create_index(op.f("ix_maite_prompt_runs_task_type"), "maite_prompt_runs", ["task_type"])
    op.create_index(op.f("ix_maite_prompt_runs_validation_status"), "maite_prompt_runs", ["validation_status"])

    op.create_table(
        "maite_task_references",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("task_kind", sa.String(length=32), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("reference_answer", sa.Text(), nullable=False),
        sa.Column("reference_strategy", sa.Text(), nullable=False, server_default=""),
        sa.Column("success_criteria", sa.Text(), nullable=False, server_default=""),
        sa.Column("learning_context", pg.JSONB(), nullable=False, server_default=_JSONB_OBJ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_maite_task_references_task_kind"), "maite_task_references", ["task_kind"])
    op.create_index(op.f("ix_maite_task_references_task_id"), "maite_task_references", ["task_id"])


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("maite_problems"):
        _create_maite_problems()
    if not inspector.has_table("maite_inquiry_sessions"):
        _create_maite_inquiry_sessions()
    if not inspector.has_table("maite_problem_analyses"):
        _create_stage_tables()
    if not inspector.has_table("maite_session_reports"):
        _create_artifact_tables()


def downgrade() -> None:
    """Additive-only migration; downgrading risks dropping Maite data on legacy DBs."""
