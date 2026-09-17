"""School OpenAI Chat Completions adapter (official /v1/chat/completions)."""

from __future__ import annotations

import logging
from typing import Any, AsyncGenerator, Dict, List, NoReturn, Optional

from openai import APIStatusError, AsyncOpenAI, RateLimitError

from clients.llm.base import (
    as_openai_chat_messages,
    extract_usage_from_openai_completion,
    extract_usage_from_stream_chunk,
)
from services.infrastructure.http.error_handler import (
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from services.llm.error_parsers.org_custom_llm_error_parser import (
    parse_error_json,
    raise_org_custom_llm_http_error,
)
from services.llm.org_custom_llm_constants import API_TYPE_OPENAI_CHAT
from services.llm.org_custom_llm_urls import openai_chat_base_url
from services.utils.error_types import BACKGROUND_INFRA_ERRORS

logger = logging.getLogger(__name__)

_PROVIDER = API_TYPE_OPENAI_CHAT


class OrgOpenAIChatClient:
    """Official Chat Completions client parameterized by school credentials."""

    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        self.model_name = model
        self.default_temperature = 0.7
        root = openai_chat_base_url(base_url)
        self.client = AsyncOpenAI(api_key=api_key, base_url=root, timeout=60)

    async def chat_completion(
        self,
        messages: List[Dict],
        temperature: Optional[float] = None,
        max_tokens: int = 1000,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """POST official chat.completions and return {content, usage}."""
        del kwargs
        try:
            completion = await self.client.chat.completions.create(
                model=self.model_name,
                messages=as_openai_chat_messages(messages),
                temperature=self.default_temperature if temperature is None else temperature,
                max_tokens=max_tokens,
            )
        except RateLimitError as exc:
            raise LLMRateLimitError(str(exc)) from exc
        except APIStatusError as exc:
            self._raise_status_error(exc)
        except BACKGROUND_INFRA_ERRORS as exc:
            raise LLMTimeoutError(str(exc)) from exc
        content = ""
        if completion.choices:
            content = completion.choices[0].message.content or ""
        if not content:
            raise LLMProviderError(
                "OpenAI Chat returned empty content",
                provider=_PROVIDER,
                error_code="empty_content",
            )
        return {
            "content": content,
            "usage": extract_usage_from_openai_completion(completion),
        }

    async def probe(self) -> None:
        """Official ping: HTTP success is enough (max_tokens=1 may be empty)."""
        try:
            await self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": "ping"}],
                temperature=0,
                max_tokens=1,
            )
        except RateLimitError as exc:
            raise LLMRateLimitError(str(exc)) from exc
        except APIStatusError as exc:
            self._raise_status_error(exc)
        except BACKGROUND_INFRA_ERRORS as exc:
            raise LLMTimeoutError(str(exc)) from exc

    async def async_stream_chat_completion(
        self,
        messages: List[Dict],
        temperature: Optional[float] = None,
        max_tokens: int = 1000,
        enable_thinking: bool = False,
        **kwargs: Any,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream official chat.completions tokens."""
        del enable_thinking, kwargs
        try:
            stream = await self.client.chat.completions.create(
                model=self.model_name,
                messages=as_openai_chat_messages(messages),
                temperature=self.default_temperature if temperature is None else temperature,
                max_tokens=max_tokens,
                stream=True,
            )
            last_usage: Optional[Dict[str, int]] = None
            async for chunk in stream:
                usage = extract_usage_from_stream_chunk(chunk)
                if usage:
                    last_usage = usage
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    yield {"type": "token", "content": delta.content}
            if last_usage:
                yield {"type": "usage", "usage": last_usage}
        except RateLimitError as exc:
            raise LLMRateLimitError(str(exc)) from exc
        except APIStatusError as exc:
            self._raise_status_error(exc)

    def _raise_status_error(self, exc: APIStatusError) -> NoReturn:
        """Map OpenAI SDK HTTP errors onto official envelopes."""
        raw = ""
        body: Dict[str, Any] = {}
        response = getattr(exc, "response", None)
        if response is not None and hasattr(response, "text"):
            raw = str(response.text or "")
            body = parse_error_json(raw)
        sdk_body = getattr(exc, "body", None)
        if not body and isinstance(sdk_body, dict):
            body = sdk_body
        raise_org_custom_llm_http_error(
            int(getattr(exc, "status_code", 400) or 400),
            raw or str(exc),
            provider=_PROVIDER,
            error_data=body or None,
        )
