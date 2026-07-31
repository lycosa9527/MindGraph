"""
LLM adapter for Maite learning prompts.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
from typing import Any, AsyncGenerator, Dict, List, Optional

from services.llm import llm_service
from services.maite.llm.router import route

logger = logging.getLogger(__name__)


class MaiteLLMAdapter:
    """Thin async wrapper around ``llm_service`` for Maite tasks."""

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        user_id: Optional[int],
        organization_id: Optional[int],
        endpoint_path: str,
        task_type: str,
        response_format: Optional[Dict[str, str]] = None,
        image_data_url: Optional[str] = None,
        max_tokens: int = 4000,
        **kwargs: Any,
    ) -> str:
        """Run a single non-streaming completion."""
        route_ctx = route(task_type, has_image=image_data_url is not None)
        messages = self._build_messages(
            user_prompt=user_prompt,
            image_data_url=image_data_url,
        )
        fmt = response_format or {"type": "json_object"}
        return await llm_service.chat(
            system_message=system_prompt,
            messages=messages,
            model=route_ctx.model,
            max_tokens=max_tokens,
            user_id=user_id,
            organization_id=organization_id,
            request_type="maite_learning",
            endpoint_path=endpoint_path,
            use_knowledge_base=False,
            response_format=fmt,
            **kwargs,
        )

    async def stream(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        user_id: Optional[int],
        organization_id: Optional[int],
        endpoint_path: str,
        task_type: str,
        image_data_url: Optional[str] = None,
        max_tokens: int = 4000,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        """Stream text chunks from the LLM."""
        route_ctx = route(task_type, has_image=image_data_url is not None)
        messages = self._build_messages(
            user_prompt=user_prompt,
            image_data_url=image_data_url,
        )
        async for chunk in llm_service.chat_stream(
            system_message=system_prompt,
            messages=messages,
            model=route_ctx.model,
            max_tokens=max_tokens,
            user_id=user_id,
            organization_id=organization_id,
            request_type="maite_learning",
            endpoint_path=endpoint_path,
            use_knowledge_base=False,
            **kwargs,
        ):
            if isinstance(chunk, str) and chunk:
                yield chunk
            elif isinstance(chunk, dict):
                content = chunk.get("content")
                if isinstance(content, str) and content:
                    yield content

    @staticmethod
    def _build_messages(
        *,
        user_prompt: str,
        image_data_url: Optional[str],
    ) -> List[Dict[str, Any]]:
        if not image_data_url:
            return [{"role": "user", "content": user_prompt}]
        multimodal: List[Dict[str, Any]] = [
            {"type": "text", "text": user_prompt},
            {"type": "image_url", "image_url": {"url": image_data_url}},
        ]
        return [{"role": "user", "content": multimodal}]
