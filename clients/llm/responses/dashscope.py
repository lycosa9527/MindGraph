"""DashScope Responses API adapter (httpx streaming)."""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncGenerator, Dict, List

import httpx

from clients.llm.http_client_manager import get_httpx_manager
from clients.llm.responses.dashscope_events import normalize_responses_event
from clients.llm.responses.types import ResponsesRequest
from config.dashscope_urls import build_dashscope_headers
from config.settings import config
from services.infrastructure.http.error_handler import (
    LLMAccessDeniedError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from services.llm.error_parsers.dashscope_error_parser import parse_and_raise_dashscope_error

logger = logging.getLogger(__name__)


def _headers() -> Dict[str, str]:
    return build_dashscope_headers(
        config.QWEN_API_KEY,
        workspace_id=config.DASHSCOPE_WORKSPACE_ID,
    )


def _tool_objects(names: List[str]) -> List[Dict[str, str]]:
    return [{"type": name} for name in names]


def _build_payload(request: ResponsesRequest) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "model": request.model,
        "input": request.input,
        "tools": _tool_objects(request.canonical_tools()),
        "stream": True,
        "enable_thinking": request.enable_thinking,
        "max_output_tokens": request.max_output_tokens,
    }
    if request.temperature is not None:
        payload["temperature"] = request.temperature
    if request.extra:
        payload.update(request.extra)
    return payload


class DashScopeResponsesClient:
    """POST ``/compatible-mode/v1/responses`` and normalize the SSE stream."""

    def __init__(self) -> None:
        self.api_url = config.QWEN_RESPONSES_URL
        self.timeout = 30
        self.stream_timeout = 300

    async def stream(self, request: ResponsesRequest) -> AsyncGenerator[Dict[str, Any], None]:
        """POST one Responses turn and yield normalized events."""
        payload = _build_payload(request)
        headers = _headers()
        client = await get_httpx_manager().get_client(
            "qwen-responses",
            self.api_url,
            self.timeout,
            self.stream_timeout,
        )
        try:
            async with client.stream("POST", self.api_url, json=payload, headers=headers) as response:
                if response.status_code != 200:
                    await self._raise_http_error(response)
                    return
                async for line in response.aiter_lines():
                    event = self._parse_sse_line(line)
                    if event is None:
                        continue
                    for normalized in normalize_responses_event(event):
                        yield normalized
        except httpx.TimeoutException as exc:
            logger.error("Responses streaming timeout")
            raise LLMTimeoutError("Qwen Responses streaming timeout") from exc
        except httpx.HTTPError as exc:
            logger.error("Responses streaming HTTP error: %s", exc)
            raise LLMProviderError(
                f"Qwen Responses HTTP error: {exc}",
                provider="qwen",
                error_code="HTTPError",
            ) from exc

    async def _raise_http_error(self, response: Any) -> None:
        error_bytes = await response.aread()
        error_text = error_bytes.decode("utf-8")
        logger.error("Responses stream error %s: %s", response.status_code, error_text)
        try:
            error_data = json.loads(error_text)
        except json.JSONDecodeError as exc:
            if response.status_code == 429:
                raise LLMRateLimitError(f"Qwen rate limit: {error_text}") from exc
            if response.status_code == 401:
                raise LLMAccessDeniedError(
                    f"Unauthorized: {error_text}",
                    provider="qwen",
                    error_code="Unauthorized",
                ) from exc
            raise LLMProviderError(
                f"Qwen Responses error ({response.status_code}): {error_text}",
                provider="qwen",
                error_code=f"HTTP{response.status_code}",
            ) from exc
        parse_and_raise_dashscope_error(response.status_code, error_text, error_data)

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
            logger.debug("[DashScopeResponses] Skip non-JSON SSE line")
            return None
        if isinstance(parsed, dict):
            return parsed
        return None
