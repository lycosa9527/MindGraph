"""
Maite problem analysis domain service.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.maite_stages import MaiteProblemAnalysis
from repositories.maite.problems_repo import MaiteProblemsRepository
from repositories.maite.sessions_repo import MaiteSessionsRepository
from repositories.maite.stages_repo import MaiteStagesRepository
from services.maite.domain.errors import MaiteNotFoundError
from services.maite.domain.json_helpers import parse_llm_json
from services.maite.llm.adapter import MaiteLLMAdapter
from services.maite.prompts.registry import PromptRegistry, get_prompt_registry

logger = logging.getLogger(__name__)


class AnalysisService:
    """Run LLM problem analysis and persist results."""

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

    async def analyze_session(
        self,
        session_id: int,
        *,
        user_id: int,
        organization_id: Optional[int],
        endpoint_path: str,
    ) -> dict[str, Any]:
        """Run LLM analysis for the session problem and persist results."""
        inquiry = await self._sessions.get_owned(session_id, user_id)
        if inquiry is None:
            raise MaiteNotFoundError("Session not found")
        problem = await self._problems.get_by_id(inquiry.problem_id)
        if problem is None:
            raise MaiteNotFoundError("Problem not found")
        rendered = self._prompts.render(
            "problem_analysis",
            {
                "problem_text": problem.clean_text,
                "subject": problem.subject,
            },
        )
        raw = await self._llm.complete(
            rendered.system_prompt,
            rendered.user_prompt,
            user_id=user_id,
            organization_id=organization_id,
            endpoint_path=endpoint_path,
            task_type="problem_analysis",
        )
        parsed = parse_llm_json(
            raw,
            fallback={
                "knowledge_points": [],
                "methods": [],
                "problem_type": "综合题",
                "difficulty": problem.difficulty or "中等",
                "core_goal": "完成题目求解",
                "possible_block_risks": [],
                "geometry_required": False,
                "mvp_recommended": True,
                "mvp_notice": "",
            },
        )
        existing_rows = await self._stages.analysis.get_all(
            filters=[MaiteProblemAnalysis.problem_id == problem.id],
            limit=1,
        )
        existing = existing_rows[0] if existing_rows else None
        if existing is None:
            row = MaiteProblemAnalysis(
                problem_id=problem.id,
                knowledge_points=parsed.get("knowledge_points") or [],
                methods=parsed.get("methods") or [],
                problem_type=str(parsed.get("problem_type") or "综合题"),
                difficulty=str(parsed.get("difficulty") or problem.difficulty or "中等"),
                core_goal=str(parsed.get("core_goal") or ""),
                possible_block_risks=parsed.get("possible_block_risks") or [],
                geometry_required=bool(parsed.get("geometry_required")),
                mvp_recommended=bool(parsed.get("mvp_recommended", True)),
                mvp_notice=str(parsed.get("mvp_notice") or ""),
            )
            saved = await self._stages.analysis.create(row)
        else:
            saved = await self._stages.analysis.update_by_id(
                existing.id,
                knowledge_points=parsed.get("knowledge_points") or [],
                methods=parsed.get("methods") or [],
                problem_type=str(parsed.get("problem_type") or existing.problem_type),
                difficulty=str(parsed.get("difficulty") or existing.difficulty),
                core_goal=str(parsed.get("core_goal") or existing.core_goal),
                possible_block_risks=parsed.get("possible_block_risks") or [],
                geometry_required=bool(parsed.get("geometry_required")),
                mvp_recommended=bool(parsed.get("mvp_recommended", True)),
                mvp_notice=str(parsed.get("mvp_notice") or ""),
            )
        if inquiry.status == "created":
            await self._sessions.update_by_id(
                inquiry.id,
                status="analyzed",
                current_stage="analysis",
                updated_at=datetime.now(UTC),
            )
        return self._row_dict(saved)

    @staticmethod
    def _row_dict(row: Any) -> dict[str, Any]:
        if row is None:
            return {}
        table = getattr(row, "__table__", None)
        if table is None:
            return {}
        return {col.name: getattr(row, col.name) for col in table.columns}
