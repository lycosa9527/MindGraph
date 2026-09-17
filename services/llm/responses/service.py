"""Responses API service: budget, rate limit, coins, then stream."""

from __future__ import annotations

import logging
import time
from typing import Any, AsyncGenerator, Dict, List, Optional

from clients.llm.org_custom.factory import build_org_custom_llm_client
from clients.llm.responses.base import BaseResponsesClient
from clients.llm.responses.types import ResponsesInput, ResponsesRequest
from config.settings import config
from services.auth.thinking_coin.token_usage_link import build_token_usage_snapshot
from services.auth.thinking_coin.usage_wire import (
    assert_llm_usage_budget,
    thinking_coin_post_llm_success,
    thinking_coins_apply_to_user,
)
from services.infrastructure.http.error_handler import LLMServiceError
from services.llm import llm_service
from services.llm.llm_utils import LLMUtils
from services.llm.org_custom_client import stream_chat_as_responses_events, uses_official_responses
from services.llm.org_custom_config import load_org_custom_llm_config
from services.llm.responses.registry import get_responses_registry
from services.utils.error_types import LLM_PIPELINE_ERRORS

_STREAM_FAILURES = (*LLM_PIPELINE_ERRORS, LLMServiceError)

logger = logging.getLogger(__name__)

DEFAULT_PROVIDER = "qwen"
DEFAULT_MAX_OUTPUT_TOKENS = 4096


def _optional_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _responses_input_to_messages(value: ResponsesInput) -> List[Dict[str, Any]]:
    if isinstance(value, str):
        return [{"role": "user", "content": value}]
    messages: List[Dict[str, Any]] = []
    for item in value:
        if isinstance(item, dict):
            messages.append(item)
    if not messages:
        return [{"role": "user", "content": "ping"}]
    return messages


def _request_type(value: Any) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return "mindmap_node_explain"


def _token_int(usage: Dict[str, Any] | None, *keys: str) -> int:
    if not usage:
        return 0
    for key in keys:
        raw = usage.get(key)
        if isinstance(raw, bool) or not isinstance(raw, int):
            continue
        return max(0, raw)
    return 0


def _log_usage(
    model: str,
    usage_data: Dict[str, Any] | None,
    metadata: Dict[str, Any],
    duration: float,
    *,
    billed: bool,
) -> None:
    input_tokens = _token_int(usage_data, "input_tokens", "prompt_tokens")
    output_tokens = _token_int(usage_data, "output_tokens", "completion_tokens")
    total_tokens = _token_int(usage_data, "total_tokens")
    if total_tokens <= 0:
        total_tokens = input_tokens + output_tokens
    logger.info(
        "[ResponsesService] usage type=%s model=%s in=%d out=%d total=%d duration=%.2fs billed=%s session=%s",
        _request_type(metadata.get("request_type")),
        model,
        input_tokens,
        output_tokens,
        total_tokens,
        duration,
        billed,
        metadata.get("session_id") or "-",
    )


class _ServiceHolder:
    """Holds the singleton Responses service."""

    instance: "LLMResponsesService | None" = None


class LLMResponsesService:
    """Provider-neutral Responses stream with the same billing hooks as chat."""

    async def stream(
        self,
        *,
        prompt: str,
        tools: List[str],
        model: Optional[str] = None,
        provider: str = DEFAULT_PROVIDER,
        enable_thinking: bool = True,
        max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
        temperature: Optional[float] = None,
        user_id: Optional[int] = None,
        organization_id: Optional[int] = None,
        request_type: str = "mindmap_node_explain",
        diagram_type: Optional[str] = None,
        endpoint_path: Optional[str] = None,
        session_id: Optional[str] = None,
        input_messages: Optional[ResponsesInput] = None,
        bill_usage: bool = True,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Yield normalized Responses events and record usage / coins."""
        start_time = time.time()
        physical_model = (model or config.QWEN_MODEL_NODE_EXPLAIN).strip() or "qwen3.8-flash"
        await assert_llm_usage_budget(
            user_id,
            organization_id,
            request_type,
            estimated_tokens=max_output_tokens,
        )
        request_input = input_messages if input_messages is not None else prompt
        request = ResponsesRequest(
            model=physical_model,
            input=request_input,
            tools=tools,
            enable_thinking=enable_thinking,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
        )
        org_config = await load_org_custom_llm_config(organization_id)
        metrics_provider = org_config.api_type if org_config is not None else "dashscope"
        if org_config is not None and not uses_official_responses(org_config):
            chat_client = build_org_custom_llm_client(org_config)
            physical_model = org_config.model
            usage_data: Dict[str, Any] | None = None
            metadata = {
                "user_id": user_id,
                "organization_id": organization_id,
                "request_type": request_type,
                "diagram_type": diagram_type,
                "endpoint_path": endpoint_path,
                "session_id": session_id,
            }
            try:
                async for event in stream_chat_as_responses_events(
                    chat_client,
                    _responses_input_to_messages(request_input),
                    temperature=temperature,
                    max_output_tokens=max_output_tokens,
                ):
                    if event.get("type") == "usage" and isinstance(event.get("usage"), dict):
                        usage_data = event["usage"]
                    yield event
                duration = time.time() - start_time
                await self._record_success(
                    physical_model,
                    usage_data,
                    metadata,
                    duration,
                    bill_usage=bill_usage,
                    provider=metrics_provider,
                )
            except _STREAM_FAILURES as exc:
                duration = time.time() - start_time
                detail = LLMUtils.format_request_failure(exc)
                await llm_service.metrics_tracker.track_all(
                    model=physical_model,
                    usage_data=None,
                    metadata=metadata,
                    provider=metrics_provider,
                    load_balancer=llm_service.load_balancer,
                    success=False,
                    duration=duration,
                    error=detail,
                )
                raise
            return
        if org_config is not None:
            physical_model = org_config.model
            request.model = physical_model
            request.tools = []
            request.enable_thinking = False
            client = build_org_custom_llm_client(org_config)
            rate_limiter = None
        else:
            client = get_responses_registry().get_client(provider)
            rate_limiter = LLMUtils.get_rate_limiter(
                model=provider,
                actual_model=physical_model,
                provider="dashscope",
                rate_limiter=llm_service.rate_limiter,
                load_balancer_rate_limiter=llm_service.load_balancer_rate_limiter,
                kimi_rate_limiter=getattr(llm_service, "kimi_rate_limiter", None),
                doubao_rate_limiter=getattr(llm_service, "doubao_rate_limiter", None),
            )
        usage_data = None
        stream_error = ""
        metadata = {
            "user_id": user_id,
            "organization_id": organization_id,
            "request_type": request_type,
            "diagram_type": diagram_type,
            "endpoint_path": endpoint_path,
            "session_id": session_id,
        }
        try:
            async for event in self._iter_events(client, request, rate_limiter):
                if event.get("type") == "usage":
                    raw_usage = event.get("usage")
                    if isinstance(raw_usage, dict):
                        usage_data = raw_usage
                    yield event
                    continue
                if event.get("type") == "error":
                    message = event.get("content")
                    if isinstance(message, str) and message.strip():
                        stream_error = message.strip()
                yield event
            duration = time.time() - start_time
            if stream_error:
                await llm_service.metrics_tracker.track_all(
                    model=physical_model,
                    usage_data=None,
                    metadata=metadata,
                    provider=metrics_provider,
                    load_balancer=llm_service.load_balancer,
                    success=False,
                    duration=duration,
                    error=stream_error,
                )
                return
            await self._record_success(
                physical_model,
                usage_data,
                metadata,
                duration,
                bill_usage=bill_usage,
                provider=metrics_provider,
            )
        except _STREAM_FAILURES as exc:
            duration = time.time() - start_time
            detail = LLMUtils.format_request_failure(exc)
            logger.error(
                "[ResponsesService] stream failed after %.2fs: %s",
                duration,
                detail,
            )
            await llm_service.metrics_tracker.track_all(
                model=physical_model,
                usage_data=None,
                metadata=metadata,
                provider=metrics_provider,
                load_balancer=llm_service.load_balancer,
                success=False,
                duration=duration,
                error=detail,
            )
            raise

    async def _iter_events(
        self,
        client: BaseResponsesClient,
        request: ResponsesRequest,
        rate_limiter: Any,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        if rate_limiter:
            async with rate_limiter:
                async for event in client.stream(request):
                    yield event
            return
        async for event in client.stream(request):
            yield event

    async def _record_success(
        self,
        model: str,
        usage_data: Dict[str, Any] | None,
        metadata: Dict[str, Any],
        duration: float,
        bill_usage: bool = True,
        provider: str = "dashscope",
    ) -> None:
        if not bill_usage:
            await llm_service.metrics_tracker.track_all(
                model=model,
                usage_data=usage_data,
                metadata=metadata,
                provider=provider,
                load_balancer=llm_service.load_balancer,
                success=True,
                duration=duration,
            )
            _log_usage(model, usage_data, metadata, duration, billed=False)
            return
        coins_user = await thinking_coins_apply_to_user(
            _optional_int(metadata.get("user_id")),
            _optional_int(metadata.get("organization_id")),
        )
        await llm_service.metrics_tracker.track_all(
            model=model,
            usage_data=usage_data,
            metadata=metadata,
            provider=provider,
            load_balancer=llm_service.load_balancer,
            success=True,
            duration=duration,
            skip_token_buffer=coins_user,
        )
        _log_usage(model, usage_data, metadata, duration, billed=bill_usage)
        usage_snapshot = (
            build_token_usage_snapshot(usage_data, metadata, model, duration) if coins_user and usage_data else None
        )
        await thinking_coin_post_llm_success(
            _optional_int(metadata.get("user_id")),
            _optional_int(metadata.get("organization_id")),
            _request_type(metadata.get("request_type")),
            usage_snapshot,
        )


def get_responses_service() -> LLMResponsesService:
    """Return the shared Responses service."""
    if _ServiceHolder.instance is None:
        _ServiceHolder.instance = LLMResponsesService()
    return _ServiceHolder.instance
