"""Unit tests for per-org custom LLM URLs, errors, and admin apply."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from models.domain.auth import Organization
from routers.auth.admin.organization_custom_llm import (
    apply_custom_llm_on_update,
    custom_llm_list_fields,
)
from services.infrastructure.http.error_handler import (
    LLMAccessDeniedError,
    LLMInvalidParameterError,
    LLMModelNotFoundError,
    LLMProviderError,
    LLMQuotaExhaustedError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from services.llm.error_parsers.org_custom_llm_error_parser import (
    raise_org_custom_llm_http_error,
    raise_org_custom_llm_stream_error,
)
from services.llm.org_custom_anthropic import split_anthropic_messages
from services.llm.org_custom_client import collapse_org_custom_models, usage_model_name
from services.llm.org_custom_config import config_from_org, session_custom_llm_fields
from services.llm.org_custom_llm_constants import (
    API_TYPE_OPENAI_CHAT,
    API_TYPE_PLATFORM,
    OrgCustomLlmConfig,
)
from services.llm.org_custom_llm_urls import (
    anthropic_messages_url,
    normalize_api_root,
    openai_responses_url,
    validated_api_root,
)
from services.redis.cache.redis_org_cache import OrganizationCache


def test_validated_api_root_rejects_non_http_and_metadata() -> None:
    """School URLs must be http(s) with a host; campus LAN is allowed."""
    assert validated_api_root("https://llm.school.edu/v1") == "https://llm.school.edu/v1"
    assert validated_api_root("http://10.0.0.8:8000/v1") == "http://10.0.0.8:8000/v1"
    assert validated_api_root("file:///etc/passwd") == ""
    assert validated_api_root("javascript:alert(1)") == ""
    assert validated_api_root("https://169.254.169.254/latest") == ""
    assert validated_api_root("https://user:pass@llm.school.edu/v1") == ""


def test_normalize_api_root_strips_protocol_suffix() -> None:
    """Admins may paste a full endpoint; we store the API root."""
    assert normalize_api_root("https://llm.school.edu/v1/chat/completions/") == "https://llm.school.edu/v1"
    assert openai_responses_url("https://api.openai.com/v1") == "https://api.openai.com/v1/responses"
    assert anthropic_messages_url("https://api.anthropic.com") == "https://api.anthropic.com/v1/messages"
    assert anthropic_messages_url("https://gw.school.edu/v1") == "https://gw.school.edu/v1/messages"


def test_openai_error_envelope_maps_official_types() -> None:
    """OpenAI {error:{type,code,message}} maps onto existing LLM* classes."""
    with pytest.raises(LLMAccessDeniedError):
        raise_org_custom_llm_http_error(
            401,
            (
                '{"error":{"message":"Incorrect API key provided",'
                '"type":"invalid_request_error","code":"invalid_api_key"}}'
            ),
            provider="openai_chat",
        )
    with pytest.raises(LLMModelNotFoundError):
        raise_org_custom_llm_http_error(
            404,
            '{"error":{"message":"The model does not exist","type":"invalid_request_error","code":"model_not_found"}}',
            provider="openai_chat",
        )
    with pytest.raises(LLMQuotaExhaustedError):
        raise_org_custom_llm_http_error(
            429,
            (
                '{"error":{"message":"You exceeded your current quota",'
                '"type":"insufficient_quota","code":"insufficient_quota"}}'
            ),
            provider="openai_chat",
        )
    with pytest.raises(LLMRateLimitError):
        raise_org_custom_llm_http_error(
            429,
            '{"error":{"message":"Rate limit reached","type":"rate_limit_error","code":"slow_down"}}',
            provider="openai_chat",
        )
    with pytest.raises(LLMInvalidParameterError):
        raise_org_custom_llm_http_error(
            400,
            '{"error":{"message":"Invalid model","type":"invalid_request_error","param":"model"}}',
            provider="openai_chat",
        )


def test_anthropic_error_envelope_maps_official_types() -> None:
    """Anthropic {type:error,error:{type,message}} maps onto existing LLM* classes."""
    with pytest.raises(LLMAccessDeniedError):
        raise_org_custom_llm_http_error(
            401,
            '{"type":"error","error":{"type":"authentication_error","message":"invalid x-api-key"}}',
            provider="anthropic_messages",
        )
    with pytest.raises(LLMQuotaExhaustedError):
        raise_org_custom_llm_http_error(
            402,
            '{"type":"error","error":{"type":"billing_error","message":"credit balance too low"}}',
            provider="anthropic_messages",
        )
    with pytest.raises(LLMModelNotFoundError):
        raise_org_custom_llm_http_error(
            404,
            '{"type":"error","error":{"type":"not_found_error","message":"model not found"}}',
            provider="anthropic_messages",
        )
    with pytest.raises(LLMTimeoutError):
        raise_org_custom_llm_http_error(
            504,
            '{"type":"error","error":{"type":"timeout_error","message":"request timed out"}}',
            provider="anthropic_messages",
        )
    with pytest.raises(LLMInvalidParameterError):
        raise_org_custom_llm_http_error(
            413,
            '{"type":"error","error":{"type":"request_too_large","message":"payload too large"}}',
            provider="anthropic_messages",
        )


def test_stream_and_responses_envelopes_use_official_types() -> None:
    """Mid-stream events have no useful HTTP status; classify by official type/code."""
    with pytest.raises(LLMRateLimitError):
        raise_org_custom_llm_stream_error(
            {"type": "error", "error": {"type": "rate_limit_error", "message": "slow down"}},
            provider="anthropic_messages",
        )
    with pytest.raises(LLMProviderError):
        raise_org_custom_llm_stream_error(
            {"type": "error", "error": {"type": "api_error", "message": "internal error"}},
            provider="anthropic_messages",
        )
    with pytest.raises(LLMAccessDeniedError):
        raise_org_custom_llm_stream_error(
            {
                "type": "error",
                "error": {
                    "message": "Incorrect API key provided",
                    "type": "invalid_request_error",
                    "code": "invalid_api_key",
                },
            },
            provider="openai_chat",
        )
    with pytest.raises(LLMProviderError):
        raise_org_custom_llm_http_error(
            200,
            "",
            provider="openai_responses",
            error_data={
                "type": "response.failed",
                "response": {"error": {"code": "server_error", "message": "engine crashed"}},
            },
        )
    with pytest.raises(LLMAccessDeniedError):
        raise_org_custom_llm_http_error(401, "Unauthorized", provider="openai_chat")
    with pytest.raises(LLMRateLimitError):
        raise_org_custom_llm_http_error(429, "Too Many Requests", provider="openai_responses")


def test_split_anthropic_lifts_system_role() -> None:
    """Official Messages API has no system role inside messages."""
    system_text, turns = split_anthropic_messages(
        [
            {"role": "system", "content": "You are a teacher."},
            {"role": "user", "content": "Hello"},
        ]
    )
    assert system_text == "You are a teacher."
    assert turns == [{"role": "user", "content": "Hello"}]


def test_config_from_org_requires_complete_override() -> None:
    """Platform default and incomplete triples stay inactive."""
    org = Organization()
    setattr(org, "id", 1)
    setattr(org, "custom_llm_api_type", API_TYPE_OPENAI_CHAT)
    setattr(org, "custom_llm_base_url", "https://llm.school.edu/v1")
    setattr(org, "custom_llm_api_key", None)
    setattr(org, "custom_llm_model", "校本大模型")
    assert config_from_org(org) is None
    session = session_custom_llm_fields(org)
    assert session["custom_llm_enabled"] is False


def test_apply_custom_llm_platform_clears_credentials() -> None:
    """Switching back to DashScope/Volcengine clears school fields."""
    org = Organization()
    setattr(org, "id", 9)
    setattr(org, "custom_llm_api_type", API_TYPE_OPENAI_CHAT)
    setattr(org, "custom_llm_base_url", "https://llm.school.edu/v1")
    setattr(org, "custom_llm_api_key", "sk-test")
    setattr(org, "custom_llm_model", "school-llm")
    apply_custom_llm_on_update(org, {"custom_llm_api_type": API_TYPE_PLATFORM}, "en")
    assert getattr(org, "custom_llm_api_type") == API_TYPE_PLATFORM
    assert getattr(org, "custom_llm_api_key") is None
    fields = custom_llm_list_fields(org)
    assert fields["custom_llm_enabled"] is False
    assert fields["custom_llm_api_key_masked"] is None


def test_apply_custom_llm_incomplete_rejected() -> None:
    """Custom protocol without a key is not saved half-configured."""
    org = Organization()
    setattr(org, "id", 3)
    with pytest.raises(HTTPException) as exc:
        apply_custom_llm_on_update(
            org,
            {
                "custom_llm_api_type": API_TYPE_OPENAI_CHAT,
                "custom_llm_base_url": "https://llm.school.edu/v1",
                "custom_llm_model": "school-llm",
            },
            "en",
        )
    assert exc.value.status_code == 400


def test_apply_custom_llm_rejects_non_http_url() -> None:
    """file:// and metadata hosts are not stored as a school API root."""
    org = Organization()
    setattr(org, "id", 4)
    with pytest.raises(HTTPException) as exc:
        apply_custom_llm_on_update(
            org,
            {
                "custom_llm_api_type": API_TYPE_OPENAI_CHAT,
                "custom_llm_base_url": "file:///etc/passwd",
                "custom_llm_api_key": "sk-test",
                "custom_llm_model": "school-llm",
            },
            "en",
        )
    assert exc.value.status_code == 400


def test_cache_stamp_changes_when_url_or_key_changes() -> None:
    """Result cache must not reuse specs after the school endpoint or key changes."""
    first = OrgCustomLlmConfig(
        api_type=API_TYPE_OPENAI_CHAT,
        base_url="https://llm.school.edu/v1",
        api_key="sk-a",
        model="school-llm",
    )
    moved = OrgCustomLlmConfig(
        api_type=API_TYPE_OPENAI_CHAT,
        base_url="https://llm-b.school.edu/v1",
        api_key="sk-a",
        model="school-llm",
    )
    rotated = OrgCustomLlmConfig(
        api_type=API_TYPE_OPENAI_CHAT,
        base_url="https://llm.school.edu/v1",
        api_key="sk-b",
        model="school-llm",
    )
    assert first.cache_stamp != moved.cache_stamp
    assert first.cache_stamp != rotated.cache_stamp
    assert first.cache_stamp.startswith(f"{API_TYPE_OPENAI_CHAT}:")
    assert "sk-a" not in first.cache_stamp


@pytest.mark.asyncio
async def test_collapse_org_custom_models_keeps_one_alias() -> None:
    """Parallel generate must not hit the school endpoint once per canvas chip."""
    config = OrgCustomLlmConfig(
        api_type=API_TYPE_OPENAI_CHAT,
        base_url="https://llm.school.edu/v1",
        api_key="sk-test",
        model="school-llm",
    )
    with patch(
        "services.llm.org_custom_client.load_org_custom_llm_config",
        AsyncMock(return_value=config),
    ):
        collapsed = await collapse_org_custom_models(7, ["qwen", "deepseek", "doubao"])
    assert collapsed == ["qwen"]


def test_usage_model_name_uses_school_id_when_override_on() -> None:
    """Token usage must not keep the canvas qwen alias for a school endpoint."""
    assert usage_model_name("qwen", "gpt-4.1-mini", True) == "gpt-4.1-mini"
    assert usage_model_name("qwen", "gpt-4.1-mini", False) == "qwen"


def test_redis_org_hash_omits_school_api_key() -> None:
    """Warm Redis org hashes must never store the school LLM secret."""
    org = Organization()
    setattr(org, "id", 3)
    setattr(org, "code", "SCH")
    setattr(org, "name", "School")
    setattr(org, "custom_llm_api_key", "sk-secret-must-not-cache")
    serialize_org = getattr(OrganizationCache(), "_serialize_org")
    payload = serialize_org(org)
    assert "custom_llm_api_key" not in payload
    assert "sk-secret-must-not-cache" not in payload.values()
