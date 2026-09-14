"""Single-shot prompt_to_diagram LLM run used by generate_png and generate_dingtalk."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Optional

from agents.core.agent_utils import extract_json_from_response
from agents.core.prompt_understanding import PreparedGenerationPrompt, prepare_generation_prompt
from config.settings import config
from prompts import get_prompt
from services.llm import llm_service


@dataclass(frozen=True)
class PromptToDiagramRun:
    """LLM JSON plus shared prep metadata; callers normalize the spec."""

    prepared: PreparedGenerationPrompt
    formatted_prompt: str
    raw_result: Any
    usage_data: Optional[dict[str, Any]]
    started_at: float
    empty_response: bool
    missing_template: bool


async def run_prompt_to_diagram_llm(
    *,
    prompt: str,
    language: str,
    user_id: Any,
    organization_id: Any,
    api_key_id: Any,
    endpoint_path: str,
    explicit_instructions: Optional[str] = None,
) -> PromptToDiagramRun:
    """Prepare the prompt and call Qwen once."""
    prepared = prepare_generation_prompt(
        prompt,
        language,
        explicit_instructions=explicit_instructions,
    )
    template = get_prompt("prompt_to_diagram", prepared.language, "generation")
    if not template:
        return PromptToDiagramRun(
            prepared=prepared,
            formatted_prompt="",
            raw_result=None,
            usage_data=None,
            started_at=time.time(),
            empty_response=False,
            missing_template=True,
        )
    formatted = template.format(user_prompt=prepared.merged_prompt())
    started_at = time.time()
    response, usage_data = await llm_service.chat_with_usage(
        prompt=formatted,
        model="qwen",
        max_tokens=2000,
        temperature=config.LLM_TEMPERATURE,
        user_id=user_id,
        organization_id=organization_id,
        api_key_id=api_key_id,
        request_type="diagram_generation",
        endpoint_path=endpoint_path,
    )
    usage = usage_data if isinstance(usage_data, dict) else None
    if not response:
        return PromptToDiagramRun(
            prepared=prepared,
            formatted_prompt=formatted,
            raw_result=None,
            usage_data=usage,
            started_at=started_at,
            empty_response=True,
            missing_template=False,
        )
    return PromptToDiagramRun(
        prepared=prepared,
        formatted_prompt=formatted,
        raw_result=extract_json_from_response(response),
        usage_data=usage,
        started_at=started_at,
        empty_response=False,
        missing_template=False,
    )


def attach_learning_sheet_metadata(spec: dict[str, Any], is_learning_sheet: bool) -> dict[str, Any]:
    """Stamp learning-sheet flags used by Vue Flow renderers."""
    spec["is_learning_sheet"] = is_learning_sheet
    spec["hidden_node_percentage"] = 0.2 if is_learning_sheet else 0
    return spec
