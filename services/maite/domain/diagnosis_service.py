"""
Maite four-stage diagnosis domain service.

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

from models.domain.maite_stages import MaiteDiagnosisResult
from repositories.maite.problems_repo import MaiteProblemsRepository
from repositories.maite.sessions_repo import MaiteSessionsRepository
from repositories.maite.stages_repo import MaiteStagesRepository
from services.maite.domain.json_helpers import parse_llm_json
from services.maite.domain.session_guards import require_mutable_session
from services.maite.domain.transaction import commit_maite
from services.maite.events import emit_maite_session_event
from services.maite.llm.adapter import MaiteLLMAdapter
from services.maite.prompts.registry import PromptRegistry, get_prompt_registry

logger = logging.getLogger(__name__)

_AUTO_FALLBACK: dict[str, Any] = {
    "problem_analysis": {
        "knowledge_points": ["待确认"],
        "methods": ["待确认"],
        "problem_type": "综合题",
        "core_goal": "完成题目求解",
    },
    "stage_results": [
        {"stage": 1, "summary": "方向检查完成", "feedback": "请继续细化条件表。", "blocks": []},
        {"stage": 2, "summary": "知识边界检查完成", "feedback": "请核对定义与适用条件。", "blocks": []},
        {"stage": 3, "summary": "步骤链检查完成", "feedback": "请逐步验证中间输出。", "blocks": []},
        {
            "stage": 4,
            "summary": "轻量变式已生成",
            "variant_text": "将原题中的一个已知数改为参数，写出新的求解目标。",
            "blocks": [],
        },
    ],
    "final_block_report": [],
}


class DiagnosisService:
    """Auto diagnosis and stage-4 evaluation."""

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

    async def auto_diagnose(
        self,
        session_id: int,
        *,
        user_id: int,
        organization_id: Optional[int],
        student_thinking: str,
        endpoint_path: str,
    ) -> dict[str, Any]:
        """Run automatic four-stage diagnosis via LLM."""
        await self._require_owned_session(session_id, user_id)
        problem_text = await self._problem_text(session_id)
        decompose = await self._stages.decompose.get_for_session(session_id)
        rendered = self._prompts.render(
            "diagnosis_auto",
            {
                "problem_text": problem_text,
                "condition_table_json": json.dumps(decompose.condition_table if decompose else [], ensure_ascii=False),
                "step_table_json": json.dumps(decompose.step_table if decompose else [], ensure_ascii=False),
                "model_table_json": json.dumps(decompose.model_table if decompose else [], ensure_ascii=False),
                "student_thinking": student_thinking,
            },
        )
        raw = await self._llm.complete(
            rendered.system_prompt,
            rendered.user_prompt,
            user_id=user_id,
            organization_id=organization_id,
            endpoint_path=endpoint_path,
            task_type="diagnosis_auto",
        )
        parsed = parse_llm_json(raw, fallback=_AUTO_FALLBACK)
        stage_results = parsed.get("stage_results") or _AUTO_FALLBACK["stage_results"]
        final_report = parsed.get("final_block_report") or []
        existing = await self._stages.diagnosis.get_for_session(session_id)
        if existing is None:
            row = MaiteDiagnosisResult(
                session_id=session_id,
                decompose_submission_id=decompose.id if decompose else None,
                stage_results=stage_results,
                final_block_report=final_report,
            )
            saved = await self._stages.diagnosis.create(row)
        else:
            saved = await self._stages.diagnosis.update_by_id(
                existing.id,
                stage_results=stage_results,
                final_block_report=final_report,
                updated_at=datetime.now(UTC),
            )
        await commit_maite(self._session)
        await emit_maite_session_event(
            str(session_id),
            "diagnosis_progress",
            {"session_id": session_id, "stage": "auto"},
        )
        return self._row_dict(saved)

    async def finalize(
        self,
        session_id: int,
        *,
        user_id: int,
        final_block_report: list[Any],
    ) -> dict[str, Any]:
        """Persist final block report and advance to remedy stage."""
        await self._require_owned_session(session_id, user_id)
        existing = await self._stages.diagnosis.get_for_session(session_id)
        if existing is None:
            row = MaiteDiagnosisResult(
                session_id=session_id,
                stage_results=[],
                final_block_report=final_block_report,
            )
            saved = await self._stages.diagnosis.create(row)
        else:
            saved = await self._stages.diagnosis.update_by_id(
                existing.id,
                final_block_report=final_block_report,
                updated_at=datetime.now(UTC),
            )
        await self._sessions.update_by_id(
            session_id,
            current_stage="remedy",
            updated_at=datetime.now(UTC),
        )
        await commit_maite(self._session)
        return self._row_dict(saved)

    async def generate_stage_four_variant(
        self,
        session_id: int,
        *,
        user_id: int,
        organization_id: Optional[int],
        endpoint_path: str,
    ) -> dict[str, Any]:
        """Generate a light variant for stage-four practice."""
        await self._require_owned_session(session_id, user_id)
        problem_text = await self._problem_text(session_id)
        diagnosis = await self._stages.diagnosis.get_for_session(session_id)
        context = json.dumps(
            diagnosis.stage_results if diagnosis else [],
            ensure_ascii=False,
        )
        rendered = self._prompts.render(
            "diagnosis_stage_4_variant",
            {"problem_text": problem_text, "diagnosis_context": context},
        )
        raw = await self._llm.complete(
            rendered.system_prompt,
            rendered.user_prompt,
            user_id=user_id,
            organization_id=organization_id,
            endpoint_path=endpoint_path,
            task_type="diagnosis_stage_4_variant",
        )
        parsed = parse_llm_json(
            raw,
            fallback={"variant_text": "将原题条件略作变化，写出新的求解目标。"},
        )
        return parsed

    async def evaluate_stage_four(
        self,
        session_id: int,
        *,
        user_id: int,
        organization_id: Optional[int],
        variant_text: str,
        student_judgement: str,
        endpoint_path: str,
    ) -> dict[str, Any]:
        """Evaluate student judgement on a stage-four variant."""
        await self._require_owned_session(session_id, user_id)
        problem_text = await self._problem_text(session_id)
        decompose = await self._stages.decompose.get_for_session(session_id)
        diagnosis = await self._stages.diagnosis.get_for_session(session_id)
        rendered = self._prompts.render(
            "diagnosis_stage_4_evaluate",
            {
                "problem_text": problem_text,
                "student_decomposition_json": json.dumps(
                    {
                        "condition_table": decompose.condition_table if decompose else [],
                        "step_table": decompose.step_table if decompose else [],
                        "model_table": decompose.model_table if decompose else [],
                    },
                    ensure_ascii=False,
                ),
                "diagnosis_context": json.dumps(
                    diagnosis.stage_results if diagnosis else [],
                    ensure_ascii=False,
                ),
                "variant_text": variant_text,
                "student_judgement": student_judgement,
            },
        )
        raw = await self._llm.complete(
            rendered.system_prompt,
            rendered.user_prompt,
            user_id=user_id,
            organization_id=organization_id,
            endpoint_path=endpoint_path,
            task_type="diagnosis_stage_4_evaluate",
        )
        parsed = parse_llm_json(
            raw,
            fallback={
                "has_thinking_gap": False,
                "block_name": "",
                "remedy_direction": "",
                "feedback": "已记录你的判断，可继续变式练习。",
            },
        )
        await emit_maite_session_event(
            str(session_id),
            "stage_advanced",
            {"session_id": session_id, "stage": 4},
        )
        return parsed

    async def _require_owned_session(self, session_id: int, user_id: int) -> None:
        await require_mutable_session(self._sessions, session_id, user_id)

    async def _problem_text(self, session_id: int) -> str:
        row = await self._sessions.get_by_id(session_id)
        if row is None:
            return ""
        problem = await self._problems.get_by_id(row.problem_id)
        return problem.clean_text if problem else ""

    @staticmethod
    def _row_dict(row: Any) -> dict[str, Any]:
        if row is None:
            return {}
        table = getattr(row, "__table__", None)
        if table is None:
            return {}
        return {col.name: getattr(row, col.name) for col in table.columns}
