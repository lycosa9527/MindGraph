"""
Mentor decompose and follow-up domain service.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncGenerator, Dict, Optional

from services.infrastructure.http.error_handler import LLMServiceError
from services.maite.domain.json_helpers import parse_llm_json
from services.utils.error_types import JSON_PARSE_ERRORS, LLM_PIPELINE_ERRORS
from services.maite.llm.adapter import MaiteLLMAdapter
from services.maite.prompts.registry import PromptRegistry, get_prompt_registry
from services.maite.schemas.mentor import (
    MentorDecomposeInput,
    MentorDecomposeOutput,
    MentorFollowUpInput,
    MentorFollowUpOutput,
)

logger = logging.getLogger(__name__)


class MentorService:
    """Socratic mentor using Maite prompts and LLM adapter."""

    def __init__(
        self,
        *,
        llm: Optional[MaiteLLMAdapter] = None,
        prompts: Optional[PromptRegistry] = None,
    ) -> None:
        self._llm = llm or MaiteLLMAdapter()
        self._prompts = prompts or get_prompt_registry()

    async def decompose(
        self,
        payload: MentorDecomposeInput,
        *,
        user_id: Optional[int],
        organization_id: Optional[int],
        endpoint_path: str,
    ) -> dict[str, Any]:
        """Run mentor decompose and return structured guidance."""
        rendered = self._prompts.render(
            "mentor_decompose",
            {"problem_text": payload.question},
        )
        raw = await self._llm.complete(
            rendered.system_prompt,
            rendered.user_prompt,
            user_id=user_id,
            organization_id=organization_id,
            endpoint_path=endpoint_path,
            task_type="mentor_decompose",
        )
        data = parse_llm_json(raw, fallback={"next_question": "请先写出你识别的已知条件。"})
        return MentorDecomposeOutput.model_validate(data).model_dump()

    async def follow_up(
        self,
        payload: MentorFollowUpInput,
        *,
        decomposition: dict[str, Any],
        user_id: Optional[int],
        organization_id: Optional[int],
        endpoint_path: str,
    ) -> dict[str, Any]:
        """Continue mentor dialogue with follow-up guidance."""
        rendered = self._prompts.render(
            "mentor_follow_up",
            {
                "problem_text": payload.question,
                "decomposition_json": json.dumps(decomposition, ensure_ascii=False),
                "history_json": json.dumps(payload.history, ensure_ascii=False),
                "student_message": payload.reply,
            },
        )
        raw = await self._llm.complete(
            rendered.system_prompt,
            rendered.user_prompt,
            user_id=user_id,
            organization_id=organization_id,
            endpoint_path=endpoint_path,
            task_type="mentor_follow_up",
        )
        data = parse_llm_json(raw, fallback={"reply": raw.strip(), "guiding_question": ""})
        return MentorFollowUpOutput.model_validate(data).model_dump()

    async def decompose_stream(
        self,
        payload: MentorDecomposeInput,
        *,
        user_id: Optional[int],
        organization_id: Optional[int],
        endpoint_path: str,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream mentor decompose tokens as SSE event payloads."""
        rendered = self._prompts.render(
            "mentor_decompose",
            {"problem_text": payload.question},
        )
        buffer = ""
        yield {"event": "status", "data": {"phase": "streaming"}}
        try:
            async for chunk in self._llm.stream(
                rendered.system_prompt,
                rendered.user_prompt,
                user_id=user_id,
                organization_id=organization_id,
                endpoint_path=endpoint_path,
                task_type="mentor_decompose",
            ):
                buffer += chunk
                yield {"event": "preview", "data": {"text": chunk}}
            data = parse_llm_json(buffer, fallback={"next_question": "请先写出你识别的已知条件。"})
            validated = MentorDecomposeOutput.model_validate(data).model_dump()
            yield {"event": "complete", "data": validated}
        except (
            *LLM_PIPELINE_ERRORS,
            LLMServiceError,
            *JSON_PARSE_ERRORS,
            RuntimeError,
            ValueError,
            TypeError,
            KeyError,
        ) as exc:
            logger.error("Mentor decompose stream failed: %s", exc, exc_info=True)
            yield {"event": "error", "data": {"message": str(exc)}}

    async def follow_up_stream(
        self,
        payload: MentorFollowUpInput,
        *,
        decomposition: dict[str, Any],
        user_id: Optional[int],
        organization_id: Optional[int],
        endpoint_path: str,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream mentor follow-up tokens as SSE event payloads."""
        rendered = self._prompts.render(
            "mentor_follow_up",
            {
                "problem_text": payload.question,
                "decomposition_json": json.dumps(decomposition, ensure_ascii=False),
                "history_json": json.dumps(payload.history, ensure_ascii=False),
                "student_message": payload.reply,
            },
        )
        buffer = ""
        yield {"event": "status", "data": {"phase": "streaming"}}
        try:
            async for chunk in self._llm.stream(
                rendered.system_prompt,
                rendered.user_prompt,
                user_id=user_id,
                organization_id=organization_id,
                endpoint_path=endpoint_path,
                task_type="mentor_follow_up",
            ):
                buffer += chunk
                yield {"event": "preview", "data": {"text": chunk}}
            data = parse_llm_json(buffer, fallback={"reply": buffer.strip(), "guiding_question": ""})
            validated = MentorFollowUpOutput.model_validate(data).model_dump()
            yield {"event": "complete", "data": validated}
        except (
            *LLM_PIPELINE_ERRORS,
            LLMServiceError,
            *JSON_PARSE_ERRORS,
            RuntimeError,
            ValueError,
            TypeError,
            KeyError,
        ) as exc:
            logger.error("Mentor follow-up stream failed: %s", exc, exc_info=True)
            yield {"event": "error", "data": {"message": str(exc)}}
