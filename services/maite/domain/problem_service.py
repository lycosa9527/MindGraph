"""
Maite problem creation and OCR domain service.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.maite_learning import MaiteProblem
from repositories.maite.problems_repo import MaiteProblemsRepository
from services.maite.domain.json_helpers import parse_llm_json
from services.maite.domain.transaction import commit_maite
from services.maite.llm.adapter import MaiteLLMAdapter
from services.maite.prompts.registry import PromptRegistry, get_prompt_registry
from services.maite.schemas.problem import OcrResult, ProblemCreate, ProblemRead
from services.maite.uploads.storage import save_user_upload, to_data_url

logger = logging.getLogger(__name__)

PROBLEM_BANK: list[dict[str, Any]] = [
    {
        "id": "bank-1",
        "subject": "高中数学",
        "topic_tags": ["二次函数", "最值"],
        "difficulty": "中等",
        "clean_text": "已知函数 f(x)=x²-4x+3，定义域为 [0, 5]。求 f(x) 在该区间上的最小值与最大值，并说明取得最值的 x。",
    },
    {
        "id": "bank-2",
        "subject": "高中数学",
        "topic_tags": ["三角函数", "恒等变换"],
        "difficulty": "中等",
        "clean_text": "在 △ABC 中，已知 sin A : sin B : sin C = 3 : 4 : 5，求 cos C 的值，并判断该三角形的形状。",
    },
]


class ProblemService:
    """Manage Maite problems and OCR extraction."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        llm: Optional[MaiteLLMAdapter] = None,
        prompts: Optional[PromptRegistry] = None,
    ) -> None:
        self._session = session
        self._repo = MaiteProblemsRepository(session)
        self._llm = llm or MaiteLLMAdapter()
        self._prompts = prompts or get_prompt_registry()

    async def create_problem(
        self,
        payload: ProblemCreate,
        *,
        user_id: int,
        organization_id: Optional[int],
    ) -> ProblemRead:
        """Create a Maite problem for the user."""
        clean = payload.clean_text or payload.raw_text
        row = MaiteProblem(
            user_id=user_id,
            organization_id=organization_id,
            source_type=payload.source_type,
            raw_text=payload.raw_text,
            clean_text=clean,
            image_url=payload.image_url,
            subject=payload.subject,
            grade_level=payload.grade_level,
            topic_tags=payload.topic_tags,
            difficulty=payload.difficulty,
        )
        created = await self._repo.create(row)
        await commit_maite(self._session)
        logger.info(
            "[Maite] Problem created id=%s user=%s source=%s",
            created.id,
            user_id,
            payload.source_type,
        )
        return ProblemRead.model_validate(created)

    async def list_problems(self, user_id: int, *, limit: int = 50) -> list[ProblemRead]:
        """List problems owned by the user."""
        rows = await self._repo.list_for_user(user_id, limit=limit)
        return [ProblemRead.model_validate(row) for row in rows]

    def list_problem_bank(self) -> list[dict[str, Any]]:
        """Return static demo problem bank entries."""
        return list(PROBLEM_BANK)

    async def ocr_extract(
        self,
        *,
        user_id: int,
        organization_id: Optional[int],
        image_bytes: bytes,
        mime_type: str = "image/png",
        endpoint_path: str,
    ) -> OcrResult:
        """Extract problem text from an uploaded image via OCR."""
        if "png" in mime_type:
            suffix = ".png"
        elif "webp" in mime_type:
            suffix = ".webp"
        else:
            suffix = ".jpg"
        stored_path = await save_user_upload(user_id, image_bytes, suffix=suffix)
        data_url = await to_data_url(stored_path, mime_type=mime_type)
        rendered = self._prompts.render("ocr_extract", {"image_hint": stored_path})
        raw = await self._llm.complete(
            rendered.system_prompt,
            rendered.user_prompt,
            user_id=user_id,
            organization_id=organization_id,
            endpoint_path=endpoint_path,
            task_type="ocr_extract",
            image_data_url=data_url,
        )
        parsed = parse_llm_json(
            raw,
            fallback={"raw_text": raw.strip(), "clean_text": raw.strip()},
        )
        raw_text = str(parsed.get("raw_text") or parsed.get("problem_text") or raw.strip())
        clean_text = str(parsed.get("clean_text") or raw_text)
        if not clean_text.strip():
            logger.warning(
                "[Maite] OCR returned empty text user=%s path=%s",
                user_id,
                stored_path,
            )
        else:
            logger.info(
                "[Maite] OCR extracted user=%s chars=%s path=%s",
                user_id,
                len(clean_text),
                stored_path,
            )
        return OcrResult(
            raw_text=raw_text,
            clean_text=clean_text,
            stored_path=stored_path,
            confidence=parsed.get("confidence") if isinstance(parsed.get("confidence"), (int, float)) else None,
            extra={k: v for k, v in parsed.items() if k not in {"raw_text", "clean_text", "confidence"}},
        )
