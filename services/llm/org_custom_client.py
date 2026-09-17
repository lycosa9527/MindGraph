"""Resolve a school custom LLM client or fall back to the platform stack."""

from __future__ import annotations

from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

from clients.llm.org_custom.factory import build_org_custom_llm_client
from services.llm.org_custom_config import load_org_custom_llm_config
from services.llm.org_custom_llm_constants import API_TYPE_OPENAI_RESPONSES, OrgCustomLlmConfig


async def collapse_org_custom_models(
    organization_id: Optional[int],
    models: List[str],
) -> List[str]:
    """When a school override is on, keep one logical alias so we do not fan out."""
    if not models:
        return models
    config = await load_org_custom_llm_config(organization_id)
    if config is None:
        return models
    return [models[0]]


async def resolve_chat_routing(
    *,
    organization_id: Optional[int],
    model: str,
    skip_load_balancing: bool,
    client_manager: Any,
    load_balancer_helper: Any,
    load_balancer: Any,
) -> Tuple[Any, str, Optional[str], bool]:
    """
    Return (client, actual_model, provider, used_custom).

    Custom orgs skip global DashScope/Volcengine load balancing and remap
    every canvas alias to the school model name.
    """
    config = await load_org_custom_llm_config(organization_id)
    if config is not None:
        return build_org_custom_llm_client(config), config.model, config.api_type, True
    actual_model, provider = await load_balancer_helper.apply_load_balancing(
        model=model,
        skip_load_balancing=skip_load_balancing,
        load_balancer=load_balancer,
    )
    return client_manager.get_client(actual_model), actual_model, provider, False


async def stream_chat_as_responses_events(
    client: Any,
    messages: List[Dict[str, Any]],
    *,
    temperature: Optional[float],
    max_output_tokens: int,
) -> AsyncGenerator[Dict[str, Any], None]:
    """Adapt a school chat/Anthropic stream into Responses-shaped events."""
    usage: Optional[Dict[str, Any]] = None
    stream = client.async_stream_chat_completion(
        messages=messages,
        temperature=temperature,
        max_tokens=max_output_tokens,
    )
    async for chunk in stream:
        if not isinstance(chunk, dict):
            continue
        if chunk.get("type") == "usage" and isinstance(chunk.get("usage"), dict):
            usage = chunk["usage"]
            yield {"type": "usage", "usage": usage}
            continue
        if chunk.get("type") == "token":
            text = chunk.get("content")
            if isinstance(text, str) and text:
                yield {"type": "token", "content": text}
    if usage is None:
        return


def uses_official_responses(config: Optional[OrgCustomLlmConfig]) -> bool:
    """True when node-explain should call the school Responses endpoint."""
    return config is not None and config.api_type == API_TYPE_OPENAI_RESPONSES


def usage_model_name(model: str, actual_model: str, used_custom: bool) -> str:
    """Token rows use the school model id when the org override is active."""
    if used_custom:
        return actual_model
    return model
