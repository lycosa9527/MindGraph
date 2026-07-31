"""
Maite variant practice domain service.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.maite_artifacts import MaiteTaskReference
from models.domain.maite_stages import MaiteVariantTask
from repositories.maite.problems_repo import MaiteProblemsRepository
from repositories.maite.sessions_repo import MaiteSessionsRepository
from repositories.maite.stages_repo import MaiteStagesRepository
from services.maite.domain.errors import MaiteConflictError, MaiteNotFoundError
from services.maite.domain.json_helpers import parse_llm_json
from services.maite.domain.public_serializers import public_variant_task
from services.maite.domain.session_guards import require_mutable_session
from services.maite.domain.transaction import commit_maite
from services.maite.events import emit_maite_session_event
from services.maite.llm.adapter import MaiteLLMAdapter
from services.maite.prompts.registry import PromptRegistry, get_prompt_registry

logger = logging.getLogger(__name__)

_VARIANT_TYPES = (
    "condition",
    "question",
    "fusion",
    "difficulty",
)


class VariantService:
    """Generate and score variant transfer tasks."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        llm: Optional[MaiteLLMAdapter] = None,
        prompts: Optional[PromptRegistry] = None,
    ) -> None:
        self._session = session
        self._sessions = MaiteSessionsRepository(session)
        self._problems = MaiteProblemsRepository(session)
        self._stages = MaiteStagesRepository(session)
        self._llm = llm or MaiteLLMAdapter()
        self._prompts = prompts or get_prompt_registry()

    async def generate_variants(
        self,
        session_id: int,
        *,
        user_id: int,
        organization_id: Optional[int],
        endpoint_path: str,
    ) -> list[dict[str, Any]]:
        """Generate four variant tasks (or return existing ones) for a session."""
        await require_mutable_session(self._sessions, session_id, user_id)
        existing = await self._stages.variant.list_for_session(session_id)
        if existing:
            return [public_variant_task(row) for row in existing]
        problem_text = await self._problem_text(session_id)
        diagnosis = await self._stages.diagnosis.get_for_session(session_id)
        rendered = self._prompts.render(
            "variant",
            {
                "problem_text": problem_text,
                "final_block_report": json.dumps(
                    diagnosis.final_block_report if diagnosis else [],
                    ensure_ascii=False,
                ),
            },
        )
        raw = await self._llm.complete(
            rendered.system_prompt,
            rendered.user_prompt,
            user_id=user_id,
            organization_id=organization_id,
            endpoint_path=endpoint_path,
            task_type="variant",
        )
        parsed = parse_llm_json(raw, fallback={"variants": []})
        variants = parsed.get("variants") or parsed.get("tasks") or []
        if not isinstance(variants, list) or len(variants) < 4:
            variants = self._fallback_variants(problem_text)
        created: list[MaiteVariantTask] = []
        for index, item in enumerate(variants[:4]):
            if not isinstance(item, dict):
                continue
            variant_type = str(item.get("variant_type") or _VARIANT_TYPES[index % 4])
            row = MaiteVariantTask(
                session_id=session_id,
                variant_type=variant_type,
                variant_text=str(item.get("variant_text") or item.get("text") or problem_text),
                changed_part=str(item.get("changed_part") or ""),
                expected_strategy=str(item.get("expected_strategy") or ""),
                status="pending",
            )
            saved = await self._stages.variant.create(row)
            await self._store_reference(saved.id, item)
            created.append(saved)
        await self._sessions.update_by_id(
            session_id,
            current_stage="variant",
            status="in_progress",
            updated_at=datetime.now(UTC),
        )
        await commit_maite(self._session)
        return [public_variant_task(row) for row in created]

    async def submit_feedback(
        self,
        task_id: int,
        *,
        user_id: int,
        organization_id: Optional[int],
        student_answer: str,
        student_strategy: str,
        endpoint_path: str,
    ) -> dict[str, Any]:
        """Score a student variant answer and return public feedback fields."""
        task = await self._require_owned_task(task_id, user_id)
        if task.status == "submitted":
            raise MaiteConflictError("Variant task already submitted")
        problem_text = await self._problem_text(task.session_id)
        reference = await self._stages.task_reference.get_for_task("variant", task_id)
        rendered = self._prompts.render(
            "variant_feedback",
            {
                "problem_text": problem_text,
                "core_logic": task.expected_strategy,
                "transfer_invariant": task.changed_part,
                "variant_text": task.variant_text,
                "changed_part": task.changed_part,
                "answer_instruction": "写出完整作答",
                "transfer_instruction": "说明方法如何调整",
                "expected_strategy": task.expected_strategy,
                "success_criteria": reference.success_criteria if reference else "",
                "reference_answer": reference.reference_answer if reference else "",
                "reference_strategy": reference.reference_strategy if reference else "",
                "student_answer": student_answer,
                "student_strategy": student_strategy,
            },
        )
        raw = await self._llm.complete(
            rendered.system_prompt,
            rendered.user_prompt,
            user_id=user_id,
            organization_id=organization_id,
            endpoint_path=endpoint_path,
            task_type="variant_feedback",
        )
        feedback = parse_llm_json(
            raw,
            fallback={
                "summary": "已记录你的作答与迁移说明。",
                "transfer_result": "partial",
            },
        )
        public_feedback = self._strip_reference_fields(feedback)
        transfer = str(feedback.get("transfer_result") or "partial")
        updated = await self._stages.variant.update_by_id(
            task.id,
            student_answer=student_answer,
            student_strategy=student_strategy,
            ai_feedback=public_feedback,
            transfer_result=transfer,
            status="submitted",
            updated_at=datetime.now(UTC),
        )
        await commit_maite(self._session)
        await emit_maite_session_event(
            str(task.session_id),
            "variant_scored",
            {"task_id": task.id, "transfer_result": transfer},
        )
        return public_variant_task(updated)

    async def _store_reference(self, task_id: int, item: dict[str, Any]) -> None:
        ref_answer = str(item.get("reference_answer") or "")
        ref_strategy = str(item.get("reference_strategy") or item.get("expected_strategy") or "")
        if not ref_answer and not ref_strategy:
            return
        existing = await self._stages.task_reference.get_for_task("variant", task_id)
        if existing is not None:
            return
        row = MaiteTaskReference(
            task_kind="variant",
            task_id=task_id,
            reference_answer=ref_answer,
            reference_strategy=ref_strategy,
            success_criteria=str(item.get("success_criteria") or ""),
            learning_context={
                "variant_type": item.get("variant_type"),
                "expected_strategy": item.get("expected_strategy"),
            },
        )
        await self._stages.task_reference.create(row)

    @staticmethod
    def _fallback_variants(problem_text: str) -> list[dict[str, Any]]:
        return [
            {
                "variant_type": variant_type,
                "variant_text": f"【{variant_type}变式】{problem_text}",
                "changed_part": "条件或设问略作调整",
                "expected_strategy": "沿用原题方法并说明调整点",
            }
            for variant_type in _VARIANT_TYPES
        ]

    async def _require_owned_task(self, task_id: int, user_id: int) -> MaiteVariantTask:
        task = await self._stages.variant.get_by_id(task_id)
        if task is None:
            raise MaiteNotFoundError("Variant task not found")
        await require_mutable_session(self._sessions, task.session_id, user_id)
        return task

    async def _problem_text(self, session_id: int) -> str:
        row = await self._sessions.get_by_id(session_id)
        if row is None:
            return ""
        problem = await self._problems.get_by_id(row.problem_id)
        return problem.clean_text if problem else ""

    @staticmethod
    def _strip_reference_fields(data: dict[str, Any]) -> dict[str, Any]:
        cleaned = dict(data)
        for key in ("reference_answer", "reference_strategy", "success_criteria", "expected_strategy"):
            cleaned.pop(key, None)
        return cleaned
