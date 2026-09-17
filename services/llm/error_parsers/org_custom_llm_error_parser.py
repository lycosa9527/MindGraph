"""Map official OpenAI and Anthropic error envelopes onto LLM* exceptions."""

from __future__ import annotations

import json
from typing import Any, NoReturn, Optional

from services.infrastructure.http.error_handler import (
    LLMAccessDeniedError,
    LLMContentFilterError,
    LLMInvalidParameterError,
    LLMModelNotFoundError,
    LLMProviderError,
    LLMQuotaExhaustedError,
    LLMRateLimitError,
    LLMTimeoutError,
    is_llm_content_filter_text,
)

OPENAI_QUOTA_CODES = frozenset(
    {
        "insufficient_quota",
        "credit_balance_exhausted",
        "organization_spend_limit_exceeded",
        "project_spend_limit_exceeded",
        "organization_usage_limit_exceeded",
        "billing_not_active",
        "billing_hard_limit_reached",
    }
)

OPENAI_AUTH_CODES = frozenset(
    {
        "invalid_api_key",
        "invalid_authentication",
        "account_deactivated",
        "project_disabled",
    }
)

OPENAI_RATE_CODES = frozenset({"rate_limit_exceeded", "slow_down"})

OPENAI_NOT_FOUND_CODES = frozenset({"model_not_found"})

OPENAI_PARAM_CODES = frozenset(
    {
        "context_length_exceeded",
        "string_above_max_length",
        "unsupported_parameter",
        "invalid_value",
    }
)

ANTHROPIC_TYPE_TO_STATUS = {
    "invalid_request_error": 400,
    "authentication_error": 401,
    "billing_error": 402,
    "permission_error": 403,
    "not_found_error": 404,
    "request_too_large": 413,
    "rate_limit_error": 429,
    "api_error": 500,
    "timeout_error": 504,
    "overloaded_error": 529,
}


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def parse_error_json(error_text: str) -> dict[str, Any]:
    """Parse a provider error body; empty dict when not JSON."""
    try:
        parsed = json.loads(error_text)
    except (json.JSONDecodeError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _error_object(body: dict[str, Any]) -> dict[str, Any]:
    """Official ``error`` object: OpenAI top-level, or Responses ``response.error``."""
    nested = body.get("error")
    if isinstance(nested, dict):
        return nested
    response = body.get("response")
    if isinstance(response, dict):
        nested_response = response.get("error")
        if isinstance(nested_response, dict):
            return nested_response
    return body


def extract_official_error_message(body: dict[str, Any], fallback: str) -> str:
    """Official ``error.message`` from OpenAI or Anthropic envelopes."""
    error_obj = _error_object(body)
    message = error_obj.get("message")
    if isinstance(message, str) and message.strip():
        return message.strip()
    top = body.get("message")
    if isinstance(top, str) and top.strip():
        return top.strip()
    return fallback.strip() or "LLM request failed"


def _error_type_and_code(error_obj: dict[str, Any]) -> tuple[str, str]:
    error_type = error_obj.get("type")
    error_code = error_obj.get("code")
    type_text = error_type.strip() if isinstance(error_type, str) else ""
    code_text = error_code.strip() if isinstance(error_code, str) else ""
    return type_text, code_text


def raise_org_custom_llm_http_error(
    status_code: int,
    error_text: str,
    *,
    provider: str,
    error_data: Optional[dict[str, Any]] = None,
) -> NoReturn:
    """Raise the matching LLM* exception for an official HTTP or stream error body."""
    body = error_data if error_data is not None else parse_error_json(error_text)
    error_obj = _error_object(_as_dict(body))
    message = extract_official_error_message(_as_dict(body), error_text)
    error_type, error_code = _error_type_and_code(error_obj)
    param = error_obj.get("param")
    parameter = param.strip() if isinstance(param, str) and param.strip() else None
    http_status = int(status_code or 0)
    resolved_status = http_status
    if error_type in ANTHROPIC_TYPE_TO_STATUS and http_status < 400:
        resolved_status = ANTHROPIC_TYPE_TO_STATUS[error_type]
    code_for_logs = error_code or error_type or f"HTTP{resolved_status or 400}"

    if is_llm_content_filter_text(message) or error_code in {"content_filter", "content_policy"}:
        raise LLMContentFilterError(message, user_message=message)

    if (
        error_code in OPENAI_AUTH_CODES
        or error_type in {"authentication_error", "permission_error"}
        or http_status in {401, 403}
    ):
        raise LLMAccessDeniedError(message, provider=provider, error_code=code_for_logs)

    if error_code in OPENAI_NOT_FOUND_CODES or error_type == "not_found_error" or resolved_status == 404:
        raise LLMModelNotFoundError(message, provider=provider, error_code=code_for_logs)

    if (
        error_code in OPENAI_QUOTA_CODES
        or error_type in {"billing_error", "insufficient_quota"}
        or resolved_status == 402
    ):
        raise LLMQuotaExhaustedError(message, provider=provider, error_code=code_for_logs)

    if error_code in OPENAI_RATE_CODES or error_type == "rate_limit_error" or resolved_status == 429:
        raise LLMRateLimitError(message)

    if error_type == "timeout_error" or resolved_status == 504:
        raise LLMTimeoutError(message)

    if (
        error_code in OPENAI_PARAM_CODES
        or error_type in {"invalid_request_error", "request_too_large"}
        or resolved_status in {400, 413}
    ):
        raise LLMInvalidParameterError(
            message,
            parameter=parameter,
            error_code=code_for_logs,
            provider=provider,
        )

    if (
        error_type in {"api_error", "overloaded_error", "service_unavailable_error", "server_error"}
        or error_code in {"server_error", "server_is_overloaded"}
        or resolved_status >= 500
    ):
        raise LLMProviderError(message, provider=provider, error_code=code_for_logs)

    raise LLMProviderError(message, provider=provider, error_code=code_for_logs)


def raise_org_custom_llm_stream_error(payload: dict[str, Any], *, provider: str) -> NoReturn:
    """Raise from a mid-stream official error event (Responses / Anthropic SSE)."""
    body = _as_dict(payload)
    message = extract_official_error_message(body, "LLM stream failed")
    raise_org_custom_llm_http_error(0, message, provider=provider, error_data=body)
