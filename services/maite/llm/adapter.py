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
        fmt = response_format or {"type": "json_object"}
        call_kwargs = self._build_llm_kwargs(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            image_data_url=image_data_url,
            require_json_phrase=True,
        )
        call_kwargs.update(kwargs)
        # Maite keeps DashScope thinking off for latency (OCR + later stages).
        call_kwargs.pop("enable_thinking", None)
        logger.info(
            "[Maite] LLM complete task=%s model=%s user=%s path=%s sys_chars=%s user_chars=%s thinking=off",
            task_type,
            route_ctx.model,
            user_id,
            endpoint_path,
            len(system_prompt or ""),
            len(user_prompt or ""),
        )
        return await llm_service.chat(
            model=route_ctx.model,
            max_tokens=max_tokens,
            user_id=user_id,
            organization_id=organization_id,
            request_type="maite_learning",
            endpoint_path=endpoint_path,
            use_knowledge_base=False,
            response_format=fmt,
            **call_kwargs,
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
        response_format: Optional[Dict[str, str]] = None,
        max_tokens: int = 4000,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        """Stream text chunks from the LLM."""
        route_ctx = route(task_type, has_image=image_data_url is not None)
        want_json = response_format is not None and response_format.get("type") == "json_object"
        call_kwargs = self._build_llm_kwargs(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            image_data_url=image_data_url,
            require_json_phrase=want_json,
        )
        if response_format is not None:
            call_kwargs["response_format"] = response_format
        call_kwargs.update(kwargs)
        # Force thinking off for mentor/diagnosis/remedy/variant streams.
        call_kwargs.pop("enable_thinking", None)
        logger.info(
            "[Maite] LLM stream task=%s model=%s user=%s path=%s sys_chars=%s user_chars=%s thinking=off",
            task_type,
            route_ctx.model,
            user_id,
            endpoint_path,
            len(system_prompt or ""),
            len(user_prompt or ""),
        )
        first_token = True
        async for chunk in llm_service.chat_stream(
            model=route_ctx.model,
            max_tokens=max_tokens,
            user_id=user_id,
            organization_id=organization_id,
            request_type="maite_learning",
            endpoint_path=endpoint_path,
            use_knowledge_base=False,
            enable_thinking=False,
            **call_kwargs,
        ):
            text = self._chunk_text(chunk)
            if not text:
                continue
            if first_token:
                first_token = False
                logger.info(
                    "[Maite] LLM stream first token task=%s user=%s chars=%s",
                    task_type,
                    user_id,
                    len(text),
                )
            yield text

    @staticmethod
    def _ensure_json_mode_phrase(system_prompt: str, user_prompt: str) -> tuple[str, str]:
        """DashScope json_object mode requires the literal word json in messages."""
        combined = f"{system_prompt}\n{user_prompt}".lower()
        if "json" in combined:
            return system_prompt, user_prompt
        suffix = "\n只输出符合 JSON Schema 的单个 JSON 对象，不要输出其它文字。"
        return f"{system_prompt.rstrip()}{suffix}", user_prompt

    @staticmethod
    def _build_llm_kwargs(
        *,
        system_prompt: str,
        user_prompt: str,
        image_data_url: Optional[str],
        require_json_phrase: bool = False,
    ) -> Dict[str, Any]:
        """Build chat/chat_stream kwargs that keep the system prompt.

        ``llm_service`` ignores ``system_message`` when ``messages`` is set, so
        text calls use prompt+system_message; multimodal calls embed system in
        the messages array.
        """
        if require_json_phrase:
            system_prompt, user_prompt = MaiteLLMAdapter._ensure_json_mode_phrase(
                system_prompt,
                user_prompt,
            )
        if not image_data_url:
            return {
                "prompt": user_prompt,
                "system_message": system_prompt,
            }
        multimodal: List[Dict[str, Any]] = [
            {"type": "text", "text": user_prompt},
            {"type": "image_url", "image_url": {"url": image_data_url}},
        ]
        messages: List[Dict[str, Any]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": multimodal})
        return {"messages": messages}

    @staticmethod
    def _chunk_text(chunk: Any) -> str:
        if isinstance(chunk, str):
            return chunk
        if isinstance(chunk, dict):
            content = chunk.get("content")
            if isinstance(content, str):
                return content
        return ""
