"""
Maite session report domain service.

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

from models.domain.maite_artifacts import MaiteSessionReport
from repositories.maite.reports_repo import MaiteReportsRepository
from repositories.maite.sessions_repo import MaiteSessionsRepository
from services.maite.domain.errors import MaiteNotFoundError
from services.maite.domain.inquiry_service import InquiryService
from services.maite.domain.json_helpers import parse_llm_json
from services.maite.llm.adapter import MaiteLLMAdapter
from services.maite.prompts.registry import PromptRegistry, get_prompt_registry

logger = logging.getLogger(__name__)


class ReportService:
    """Build and persist inquiry session reports."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        llm: Optional[MaiteLLMAdapter] = None,
        prompts: Optional[PromptRegistry] = None,
    ) -> None:
        self._session = session
        self._sessions = MaiteSessionsRepository(session)
        self._reports = MaiteReportsRepository(session)
        self._inquiry = InquiryService(session)
        self._llm = llm or MaiteLLMAdapter()
        self._prompts = prompts or get_prompt_registry()

    async def build_report(
        self,
        session_id: int,
        *,
        user_id: int,
        organization_id: Optional[int],
        endpoint_path: str,
    ) -> dict[str, Any]:
        """Generate and persist a session report via LLM."""
        await self._require_owned_session(session_id, user_id)
        snapshot = await self._inquiry.get_snapshot(session_id, user_id=user_id)
        snapshot_json = json.dumps(snapshot.model_dump(), ensure_ascii=False, default=str)
        rendered = self._prompts.render("report", {"session_snapshot": snapshot_json})
        raw = await self._llm.complete(
            rendered.system_prompt,
            rendered.user_prompt,
            user_id=user_id,
            organization_id=organization_id,
            endpoint_path=endpoint_path,
            task_type="report",
        )
        parsed = parse_llm_json(
            raw,
            fallback={
                "report_markdown": self._fallback_markdown(snapshot.model_dump()),
                "sections": {},
            },
        )
        markdown = str(parsed.get("report_markdown") or self._fallback_markdown(snapshot.model_dump()))
        sections = parsed.get("sections") if isinstance(parsed.get("sections"), dict) else {}
        existing = await self._reports.get_for_session(session_id)
        if existing is None:
            row = MaiteSessionReport(
                session_id=session_id,
                report_markdown=markdown,
                sections=sections,
            )
            saved = await self._reports.create(row)
        else:
            saved = await self._reports.update_by_id(
                existing.id,
                report_markdown=markdown,
                sections=sections,
                updated_at=datetime.now(UTC),
            )
        return self._row_dict(saved)

    async def get_report(self, session_id: int, *, user_id: int) -> dict[str, Any]:
        """Return stored report or an empty placeholder."""
        await self._require_owned_session(session_id, user_id)
        row = await self._reports.get_for_session(session_id)
        if row is None:
            return {"report_markdown": "", "sections": {}}
        return self._row_dict(row)

    async def _require_owned_session(self, session_id: int, user_id: int) -> None:
        row = await self._sessions.get_owned(session_id, user_id)
        if row is None:
            raise MaiteNotFoundError("Session not found")

    @staticmethod
    def _fallback_markdown(snapshot: dict[str, Any]) -> str:
        session = snapshot.get("session") or {}
        problem = snapshot.get("problem") or {}
        title = session.get("title") or f"探究会话 #{session.get('id', '')}"
        stem = problem.get("clean_text") or problem.get("raw_text") or "（题目未记录）"
        return (
            f"# {title}\n\n"
            f"## 题目\n\n{stem}\n\n"
            f"## 阶段状态\n\n"
            f"- 当前阶段：{session.get('current_stage', 'unknown')}\n"
            f"- 状态：{session.get('status', 'unknown')}\n\n"
            f"## 说明\n\n"
            f"报告生成时使用结构化快照；详细诊断与变式结果见各阶段数据。\n"
        )

    @staticmethod
    def _row_dict(row: Any) -> dict[str, Any]:
        if row is None:
            return {}
        table = getattr(row, "__table__", None)
        if table is None:
            return {}
        return {col.name: getattr(row, col.name) for col in table.columns}
