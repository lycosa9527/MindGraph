"""School Anthropic Messages adapter (official POST /v1/messages)."""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx

from clients.llm.http_client_manager import get_httpx_manager
from services.infrastructure.http.error_handler import LLMProviderError, LLMTimeoutError
from services.llm.error_parsers.org_custom_llm_error_parser import (
    parse_error_json,
    raise_org_custom_llm_http_error,
    raise_org_custom_llm_stream_error,
)
from services.llm.org_custom_anthropic import message_text, split_anthropic_messages
from services.llm.org_custom_llm_constants import ANTHROPIC_VERSION, API_TYPE_ANTHROPIC
from services.llm.org_custom_llm_urls import anthropic_messages_url

logger = logging.getLogger(__name__)

_PROVIDER = API_TYPE_ANTHROPIC


def _join_text_blocks(content: Any) -> str:
    if not isinstance(content, list):
        return message_text(content)
    parts: List[str] = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            text = block.get("text")
            if isinstance(text, str) and text:
                parts.append(text)
    return "".join(parts)


def _usage_from_anthropic(raw: Any) -> Dict[str, int]:
    payload = raw if isinstance(raw, dict) else {}
    input_tokens = int(payload.get("input_tokens") or 0)
    output_tokens = int(payload.get("output_tokens") or 0)
    return {
        "prompt_tokens": input_tokens,
        "completion_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }


class OrgAnthropicMessagesClient:
    """Official Anthropic Messages client parameterized by school credentials."""

    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        self.model_name = model
        self.default_temperature = 0.7
        self.api_url = anthropic_messages_url(base_url)
        self.api_key = api_key

    def _headers(self) -> Dict[str, str]:
        return {
            "x-api-key": self.api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        }

    def _payload(
        self,
        messages: List[Dict],
        temperature: Optional[float],
        max_tokens: int,
        stream: bool,
    ) -> Dict[str, Any]:
        system_text, turns = split_anthropic_messages(messages)
        payload: Dict[str, Any] = {
            "model": self.model_name,
            "max_tokens": max(1, max_tokens),
            "messages": turns,
            "stream": stream,
        }
        if system_text:
            payload["system"] = system_text
        if temperature is not None:
            payload["temperature"] = temperature
        return payload

    async def chat_completion(
        self,
        messages: List[Dict],
        temperature: Optional[float] = None,
        max_tokens: int = 1000,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """POST official Messages and return {content, usage}."""
        del kwargs
        client = await get_httpx_manager().get_client(
            f"org-anthropic-{id(self)}",
            self.api_url,
            60.0,
            120.0,
        )
        try:
            response = await client.post(
                self.api_url,
                json=self._payload(messages, temperature, max_tokens, stream=False),
                headers=self._headers(),
            )
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError("Anthropic Messages timeout") from exc
        except httpx.HTTPError as exc:
            raise LLMProviderError(
                f"Anthropic Messages HTTP error: {exc}",
                provider=_PROVIDER,
                error_code="HTTPError",
            ) from exc
        if response.status_code != 200:
            raise_org_custom_llm_http_error(
                response.status_code,
                response.text,
                provider=_PROVIDER,
                error_data=parse_error_json(response.text),
            )
        data = response.json() if response.text else {}
        if not isinstance(data, dict):
            data = {}
        if data.get("type") == "error":
            raise_org_custom_llm_http_error(
                response.status_code,
                response.text,
                provider=_PROVIDER,
                error_data=data,
            )
        content = _join_text_blocks(data.get("content"))
        if not content:
            raise LLMProviderError(
                "Anthropic Messages returned empty content",
                provider=_PROVIDER,
                error_code="empty_content",
            )
        return {"content": content, "usage": _usage_from_anthropic(data.get("usage"))}

    async def probe(self) -> None:
        """Official ping: HTTP 200 is enough (max_tokens=1 may be empty)."""
        client = await get_httpx_manager().get_client(
            f"org-anthropic-probe-{id(self)}",
            self.api_url,
            30.0,
            60.0,
        )
        try:
            response = await client.post(
                self.api_url,
                json=self._payload(
                    [{"role": "user", "content": "ping"}],
                    temperature=0,
                    max_tokens=1,
                    stream=False,
                ),
                headers=self._headers(),
            )
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError("Anthropic Messages timeout") from exc
        except httpx.HTTPError as exc:
            raise LLMProviderError(
                f"Anthropic Messages HTTP error: {exc}",
                provider=_PROVIDER,
                error_code="HTTPError",
            ) from exc
        if response.status_code != 200:
            raise_org_custom_llm_http_error(
                response.status_code,
                response.text,
                provider=_PROVIDER,
                error_data=parse_error_json(response.text),
            )
        data = response.json() if response.text else {}
        if isinstance(data, dict) and data.get("type") == "error":
            raise_org_custom_llm_http_error(
                response.status_code,
                response.text,
                provider=_PROVIDER,
                error_data=data,
            )

    async def async_stream_chat_completion(
        self,
        messages: List[Dict],
        temperature: Optional[float] = None,
        max_tokens: int = 1000,
        enable_thinking: bool = False,
        **kwargs: Any,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream official Messages text_delta events as chat tokens."""
        del enable_thinking, kwargs
        client = await get_httpx_manager().get_client(
            f"org-anthropic-stream-{id(self)}",
            self.api_url,
            60.0,
            300.0,
        )
        try:
            async with client.stream(
                "POST",
                self.api_url,
                json=self._payload(messages, temperature, max_tokens, stream=True),
                headers=self._headers(),
            ) as response:
                if response.status_code != 200:
                    error_text = (await response.aread()).decode("utf-8")
                    raise_org_custom_llm_http_error(
                        response.status_code,
                        error_text,
                        provider=_PROVIDER,
                        error_data=parse_error_json(error_text),
                    )
                last_usage: Optional[Dict[str, int]] = None
                async for line in response.aiter_lines():
                    event = self._parse_sse_data(line)
                    if event is None:
                        continue
                    event_type = str(event.get("type") or "")
                    if event_type == "error":
                        raise_org_custom_llm_stream_error(event, provider=_PROVIDER)
                    if event_type == "content_block_delta":
                        delta = event.get("delta")
                        if isinstance(delta, dict) and delta.get("type") == "text_delta":
                            text = delta.get("text")
                            if isinstance(text, str) and text:
                                yield {"type": "token", "content": text}
                    if event_type == "message_delta":
                        usage = event.get("usage")
                        if isinstance(usage, dict):
                            last_usage = _usage_from_anthropic(usage)
                    if event_type == "message_start":
                        message = event.get("message")
                        if isinstance(message, dict) and isinstance(message.get("usage"), dict):
                            last_usage = _usage_from_anthropic(message.get("usage"))
                if last_usage:
                    yield {"type": "usage", "usage": last_usage}
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError("Anthropic Messages streaming timeout") from exc
        except httpx.HTTPError as exc:
            raise LLMProviderError(
                f"Anthropic Messages HTTP error: {exc}",
                provider=_PROVIDER,
                error_code="HTTPError",
            ) from exc

    @staticmethod
    def _parse_sse_data(line: str) -> Dict[str, Any] | None:
        if not line or not line.startswith("data:"):
            return None
        data_content = line[5:].strip()
        if not data_content:
            return None
        try:
            parsed = json.loads(data_content)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
