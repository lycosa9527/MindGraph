"""School OpenAI Responses adapter (official POST /responses)."""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx

from clients.llm.http_client_manager import get_httpx_manager
from clients.llm.responses.dashscope_events import normalize_responses_event
from clients.llm.responses.types import ResponsesRequest
from services.infrastructure.http.error_handler import LLMProviderError, LLMTimeoutError
from services.llm.error_parsers.org_custom_llm_error_parser import (
    parse_error_json,
    raise_org_custom_llm_http_error,
    raise_org_custom_llm_stream_error,
)
from services.llm.org_custom_llm_constants import API_TYPE_OPENAI_RESPONSES
from services.llm.org_custom_llm_urls import openai_responses_url

logger = logging.getLogger(__name__)

_PROVIDER = API_TYPE_OPENAI_RESPONSES


def _usage_from_responses(raw: Any) -> Dict[str, int]:
    payload = raw if isinstance(raw, dict) else {}
    input_tokens = int(payload.get("input_tokens") or payload.get("prompt_tokens") or 0)
    output_tokens = int(payload.get("output_tokens") or payload.get("completion_tokens") or 0)
    total = int(payload.get("total_tokens") or 0) or (input_tokens + output_tokens)
    return {
        "prompt_tokens": input_tokens,
        "completion_tokens": output_tokens,
        "total_tokens": total,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }


def _output_text(data: Dict[str, Any]) -> str:
    direct = data.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct
    chunks: List[str] = []
    output = data.get("output")
    if not isinstance(output, list):
        return ""
    for item in output:
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if not isinstance(part, dict):
                continue
            if part.get("type") in {"output_text", "text"}:
                text = part.get("text")
                if isinstance(text, str) and text:
                    chunks.append(text)
    return "".join(chunks)


def messages_to_responses_input(messages: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Map MindGraph chat messages to official Responses ``input`` items."""
    items: List[Dict[str, str]] = []
    for message in messages:
        role = str(message.get("role") or "user")
        if role not in {"system", "user", "assistant", "developer"}:
            role = "user"
        content = message.get("content")
        if isinstance(content, str):
            text = content
        else:
            text = json.dumps(content, ensure_ascii=False) if content is not None else ""
        if text:
            items.append({"role": role, "content": text})
    if not items:
        items.append({"role": "user", "content": "ping"})
    return items


class OrgOpenAIResponsesClient:
    """Official Responses client parameterized by school credentials."""

    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        self.model_name = model
        self.default_temperature = 0.7
        self.api_url = openai_responses_url(base_url)
        self.api_key = api_key

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _payload(
        self,
        messages: List[Dict],
        temperature: Optional[float],
        max_tokens: int,
        stream: bool,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": self.model_name,
            "input": messages_to_responses_input(messages),
            "max_output_tokens": max_tokens,
            "stream": stream,
        }
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
        """Non-stream official Responses request flattened to chat text."""
        del kwargs
        client = await get_httpx_manager().get_client(
            f"org-responses-{id(self)}",
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
            raise LLMTimeoutError("OpenAI Responses timeout") from exc
        except httpx.HTTPError as exc:
            raise LLMProviderError(
                f"OpenAI Responses HTTP error: {exc}",
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
        content = _output_text(data)
        if not content:
            raise LLMProviderError(
                "OpenAI Responses returned empty content",
                provider=_PROVIDER,
                error_code="empty_content",
            )
        return {"content": content, "usage": _usage_from_responses(data.get("usage"))}

    async def probe(self) -> None:
        """Official ping: HTTP 200 is enough (max_output_tokens=16 may be empty)."""
        client = await get_httpx_manager().get_client(
            f"org-responses-probe-{id(self)}",
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
                    max_tokens=16,
                    stream=False,
                ),
                headers=self._headers(),
            )
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError("OpenAI Responses timeout") from exc
        except httpx.HTTPError as exc:
            raise LLMProviderError(
                f"OpenAI Responses HTTP error: {exc}",
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

    async def async_stream_chat_completion(
        self,
        messages: List[Dict],
        temperature: Optional[float] = None,
        max_tokens: int = 1000,
        enable_thinking: bool = False,
        **kwargs: Any,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream official Responses events as chat tokens."""
        del enable_thinking, kwargs
        client = await get_httpx_manager().get_client(
            f"org-responses-stream-{id(self)}",
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
                async for line in response.aiter_lines():
                    event = self._parse_sse_line(line)
                    if event is None:
                        continue
                    if event.get("type") in {"error", "response.failed"}:
                        raise_org_custom_llm_stream_error(event, provider=_PROVIDER)
                    for normalized in normalize_responses_event(event):
                        yield normalized
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError("OpenAI Responses streaming timeout") from exc
        except httpx.HTTPError as exc:
            raise LLMProviderError(
                f"OpenAI Responses HTTP error: {exc}",
                provider=_PROVIDER,
                error_code="HTTPError",
            ) from exc

    async def stream(self, request: ResponsesRequest) -> AsyncGenerator[Dict[str, Any], None]:
        """ResponsesService entry: official Responses stream, text only."""
        if isinstance(request.input, str):
            messages: List[Dict] = [{"role": "user", "content": request.input}]
        elif isinstance(request.input, list):
            messages = [item for item in request.input if isinstance(item, dict)]
        else:
            messages = [{"role": "user", "content": "ping"}]
        async for event in self.async_stream_chat_completion(
            messages,
            temperature=request.temperature,
            max_tokens=request.max_output_tokens,
        ):
            yield event

    @staticmethod
    def _parse_sse_line(line: str) -> Dict[str, Any] | None:
        if not line or not line.startswith("data:"):
            return None
        data_content = line[5:].strip()
        if not data_content or data_content == "[DONE]":
            return None
        try:
            parsed = json.loads(data_content)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
