"""
Maite targeted remedy domain service.

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
from models.domain.maite_stages import MaiteRemedyTask
from repositories.maite.problems_repo import MaiteProblemsRepository
from repositories.maite.sessions_repo import MaiteSessionsRepository
from repositories.maite.stages_repo import MaiteStagesRepository
from services.maite.domain.errors import MaiteConflictError, MaiteNotFoundError
from services.maite.domain.json_helpers import parse_llm_json
from services.maite.domain.public_serializers import public_remedy_task
from services.maite.domain.session_guards import require_mutable_session
from services.maite.domain.transaction import commit_maite
from services.maite.events import emit_maite_session_event
from services.maite.llm.adapter import MaiteLLMAdapter
from services.maite.prompts.registry import PromptRegistry, get_prompt_registry

logger = logging.getLogger(__name__)

_BLOCK_TYPE_PROMPTS = {
    "knowledge_gap": "remedy_knowledge",
    "connection_break": "remedy_connection",
    "thinking_gap": "remedy_thinking",
}


class RemedyService:
    """Create and score remedy tasks without exposing reference answers."""

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

    async def create_overview_from_report(
        self,
        session_id: int,
        *,
        user_id: int,
    ) -> list[dict[str, Any]]:
        """Create remedy tasks from the diagnosis block report."""
        await require_mutable_session(self._sessions, session_id, user_id)
        existing = await self._stages.remedy.list_for_session(session_id)
        if existing:
            return [public_remedy_task(row) for row in existing]
        diagnosis = await self._stages.diagnosis.get_for_session(session_id)
        blocks = diagnosis.final_block_report if diagnosis else []
        created_rows: list[MaiteRemedyTask] = []
        for block in blocks:
            if not isinstance(block, dict):
                continue
            block_type = str(block.get("block_type") or "knowledge_gap")
            block_name = str(block.get("block_name") or block.get("name") or "待补弱点")
            row = MaiteRemedyTask(
                session_id=session_id,
                diagnosis_result_id=diagnosis.id if diagnosis else 0,
                block_type=block_type,
                block_name=block_name,
                source_block=block,
                task_payload={"status": "pending_prepare"},
                status="pending",
            )
            created_rows.append(await self._stages.remedy.create(row))
        await commit_maite(self._session)
        return [public_remedy_task(row) for row in created_rows]

    async def prepare_task(
        self,
        task_id: int,
        *,
        user_id: int,
        organization_id: Optional[int],
        endpoint_path: str,
    ) -> dict[str, Any]:
        """Generate remedy task payload via LLM without reference answers."""
        task = await self._require_owned_task(task_id, user_id)
        prompt_id = _BLOCK_TYPE_PROMPTS.get(task.block_type, "remedy_thinking")
        problem_text = await self._problem_text(task.session_id)
        block = task.source_block if isinstance(task.source_block, dict) else {}
        rendered = self._prompts.render(
            prompt_id,
            {
                "problem_text": problem_text,
                "block_name": task.block_name,
                "block_evidence": json.dumps(block.get("evidence", block), ensure_ascii=False),
                "remedy_direction": str(block.get("remedy_direction") or block.get("direction") or ""),
                "final_block_report": json.dumps([block], ensure_ascii=False),
            },
        )
        raw = await self._llm.complete(
            rendered.system_prompt,
            rendered.user_prompt,
            user_id=user_id,
            organization_id=organization_id,
            endpoint_path=endpoint_path,
            task_type=prompt_id,
        )
        parsed = parse_llm_json(
            raw,
            fallback={
                "prompt": "请写出解决该堵点所需的关键判断。",
                "answer_instruction": "写出你的推理步骤。",
            },
        )
        public_payload = self._strip_reference_fields(parsed)
        updated = await self._stages.remedy.update_by_id(
            task.id,
            task_payload=public_payload,
            status="prepared",
            updated_at=datetime.now(UTC),
        )
        await self._store_reference("remedy", task.id, parsed)
        await commit_maite(self._session)
        await emit_maite_session_event(
            str(task.session_id),
            "remedy_prepared",
            {"task_id": task.id},
        )
        return public_remedy_task(updated)

    async def submit_task(
        self,
        task_id: int,
        *,
        user_id: int,
        organization_id: Optional[int],
        student_response: str,
        student_confidence: Optional[str],
        endpoint_path: str,
    ) -> dict[str, Any]:
        """Score student remedy response and store feedback."""
        task = await self._require_owned_task(task_id, user_id)
        if task.status == "submitted":
            raise MaiteConflictError("Remedy task already submitted")
        feedback_prompt_id = self._feedback_prompt_id(task.block_type)
        problem_text = await self._problem_text(task.session_id)
        rendered = self._prompts.render(
            feedback_prompt_id,
            {
                "problem_text": problem_text,
                "block_name": task.block_name,
                "block_evidence": json.dumps(task.source_block, ensure_ascii=False),
                "task_payload": json.dumps(task.task_payload, ensure_ascii=False),
                "decomposition_context": "{}",
                "student_response": student_response,
                "student_confidence": student_confidence or "",
            },
        )
        raw = await self._llm.complete(
            rendered.system_prompt,
            rendered.user_prompt,
            user_id=user_id,
            organization_id=organization_id,
            endpoint_path=endpoint_path,
            task_type=feedback_prompt_id,
        )
        feedback = parse_llm_json(
            raw,
            fallback={"summary": "已收到你的作答，请对照关键判断继续改进。", "score": "partial"},
        )
        public_feedback = self._strip_reference_fields(feedback)
        updated = await self._stages.remedy.update_by_id(
            task.id,
            student_response=student_response,
            student_confidence=student_confidence,
            ai_feedback=public_feedback,
            status="submitted",
            updated_at=datetime.now(UTC),
        )
        await commit_maite(self._session)
        return public_remedy_task(updated)

    @staticmethod
    def _feedback_prompt_id(block_type: str) -> str:
        mapping = {
            "knowledge_gap": "remedy_knowledge_feedback",
            "connection_break": "remedy_connection_feedback",
            "thinking_gap": "remedy_thinking_feedback",
        }
        return mapping.get(block_type, "remedy_thinking_feedback")

    async def _store_reference(self, task_kind: str, task_id: int, payload: dict[str, Any]) -> None:
        ref_answer = str(payload.get("reference_answer") or "")
        ref_strategy = str(payload.get("reference_strategy") or "")
        criteria = str(payload.get("success_criteria") or "")
        if not ref_answer and not ref_strategy:
            return
        existing = await self._stages.task_reference.get_for_task(task_kind, task_id)
        if existing is not None:
            return
        row = MaiteTaskReference(
            task_kind=task_kind,
            task_id=task_id,
            reference_answer=ref_answer,
            reference_strategy=ref_strategy,
            success_criteria=criteria,
            learning_context={"source": "prepare_task"},
        )
        await self._stages.task_reference.create(row)

    async def _require_owned_task(self, task_id: int, user_id: int) -> MaiteRemedyTask:
        task = await self._stages.remedy.get_by_id(task_id)
        if task is None:
            raise MaiteNotFoundError("Remedy task not found")
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
