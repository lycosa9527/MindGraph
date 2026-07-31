"""
Mate Learning stage ORM models.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from models.domain.auth import Base


class MaiteProblemAnalysis(Base):
    """LLM analysis of a problem."""

    __tablename__ = "maite_problem_analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    problem_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("maite_problems.id", ondelete="CASCADE"), nullable=False, index=True
    )
    knowledge_points: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    methods: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    problem_type: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    difficulty: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    core_goal: Mapped[str] = mapped_column(Text, nullable=False, default="")
    possible_block_risks: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    geometry_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    mvp_recommended: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    mvp_notice: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )


class MaiteSelfAssessment(Base):
    """Student mastery self-assessment for a session."""

    __tablename__ = "maite_self_assessments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("maite_inquiry_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    items: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )


class MaiteDecomposeSubmission(Base):
    """Three reverse-decompose tables submission."""

    __tablename__ = "maite_decompose_submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("maite_inquiry_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    condition_table: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    step_table: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    model_table: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    validation_warnings: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )


class MaiteDiagnosisResult(Base):
    """Diagnosis stage results and final block report."""

    __tablename__ = "maite_diagnosis_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("maite_inquiry_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    decompose_submission_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    stage_results: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    final_block_report: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )


class MaiteRemedyTask(Base):
    """Targeted remedy task for a diagnosis block."""

    __tablename__ = "maite_remedy_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("maite_inquiry_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    diagnosis_result_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    block_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    block_name: Mapped[str] = mapped_column(String(200), nullable=False)
    source_block: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    task_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    student_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    student_confidence: Mapped[str | None] = mapped_column(String(32), nullable=True)
    ai_feedback: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )


class MaiteVariantTask(Base):
    """Variant practice task."""

    __tablename__ = "maite_variant_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("maite_inquiry_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    variant_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    variant_text: Mapped[str] = mapped_column(Text, nullable=False)
    changed_part: Mapped[str] = mapped_column(Text, nullable=False, default="")
    expected_strategy: Mapped[str] = mapped_column(Text, nullable=False, default="")
    student_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    student_strategy: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_feedback: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    transfer_result: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
