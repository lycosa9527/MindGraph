"""Build a school LLM client for an official wire format."""

from __future__ import annotations

from typing import Any

from clients.llm.org_custom.anthropic_messages import OrgAnthropicMessagesClient
from clients.llm.org_custom.openai_chat import OrgOpenAIChatClient
from clients.llm.org_custom.openai_responses import OrgOpenAIResponsesClient
from services.llm.org_custom_llm_constants import (
    API_TYPE_ANTHROPIC,
    API_TYPE_OPENAI_CHAT,
    API_TYPE_OPENAI_RESPONSES,
    OrgCustomLlmConfig,
)


def build_org_custom_llm_client(config: OrgCustomLlmConfig) -> Any:
    """Return a BaseLLMClient-compatible adapter for the school protocol."""
    if config.api_type == API_TYPE_OPENAI_RESPONSES:
        return OrgOpenAIResponsesClient(config.api_key, config.base_url, config.model)
    if config.api_type == API_TYPE_ANTHROPIC:
        return OrgAnthropicMessagesClient(config.api_key, config.base_url, config.model)
    if config.api_type == API_TYPE_OPENAI_CHAT:
        return OrgOpenAIChatClient(config.api_key, config.base_url, config.model)
    raise ValueError(f"Unsupported custom LLM type: {config.api_type}")
