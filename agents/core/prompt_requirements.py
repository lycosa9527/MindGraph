"""
Prompt requirements extraction — stage 2 of diagram generation pipeline.

Extracts clean central topic and type-native structural requirements from natural language.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional

from agents.core.agent_utils import extract_json_from_response
from prompts import get_prompt
from prompts.requirements_schemas import get_requirements_schema, normalize_diagram_type_for_requirements
from services.llm import llm_service
from services.utils.error_types import LLM_PIPELINE_ERRORS
from utils.prompt_locale import is_chinese_prompt_shell_language

logger = logging.getLogger(__name__)

StructureMode = Literal["free", "fixed"]

USER_REQUIREMENTS_MARKER_ZH = "【用户要求】"
USER_REQUIREMENTS_MARKER_EN = "User requirements:"

_CENTRAL_FIELD_BY_TYPE: Dict[str, str] = {
    "mind_map": "topic",
    "bubble_map": "topic",
    "circle_map": "topic",
    "double_bubble_map": "left",
    "tree_map": "topic",
    "brace_map": "whole",
    "flow_map": "title",
    "multi_flow_map": "event",
    "bridge_map": "topic",
    "concept_map": "topic",
}

_FIXED_NODE_KEYS_BY_TYPE: Dict[str, frozenset[str]] = {
    "mind_map": frozenset({"children"}),
    "bubble_map": frozenset({"attributes"}),
    "circle_map": frozenset({"context"}),
    "double_bubble_map": frozenset(
        {"left", "right", "similarities", "left_differences", "right_differences"}
    ),
    "tree_map": frozenset({"children", "dimension"}),
    "brace_map": frozenset({"parts", "dimension"}),
    "flow_map": frozenset({"steps"}),
    "multi_flow_map": frozenset({"causes", "effects"}),
    "bridge_map": frozenset({"analogies", "dimension"}),
    "concept_map": frozenset({"concepts"}),
}

_LIST_KEYS = frozenset(
    {
        "children",
        "attributes",
        "context",
        "similarities",
        "left_differences",
        "right_differences",
        "parts",
        "steps",
        "causes",
        "effects",
        "concepts",
    }
)


@dataclass
class ParsedRequirements:
    """Structured output from requirements extraction."""

    structure_mode: StructureMode = "free"
    central: str = ""
    fixed_nodes: Dict[str, Any] = field(default_factory=dict)
    clarity: str = "clear"
    constraints: str = ""
    diagram_type: str = "mind_map"

    def central_for_type(self, _diagram_type: Optional[str] = None) -> str:
        """Return central field value for the diagram type."""
        return self.central.strip()


@dataclass
class AgentRequirementParams:
    """Kwargs fragment for _generate_spec_with_agent."""

    structure_mode: StructureMode = "free"
    fixed_nodes: Dict[str, Any] = field(default_factory=dict)
    constraints: str = ""
    fixed_dimension: Optional[str] = None
    dimension_only_mode: Optional[bool] = None
    existing_analogies: Optional[List[Dict[str, str]]] = None
    agent_user_message_suffix: str = ""


def _topic_extraction_rules(language: str) -> str:
    text = get_prompt("topic_extraction", language, "generation")
    if not text:
        return "Extract the central subject; ignore diagram type and action words."
    marker = 'User input: "{user_prompt}"'
    if marker in text:
        return text.split(marker)[0].strip()
    marker_zh = '用户输入："{user_prompt}"'
    if marker_zh in text:
        return text.split(marker_zh)[0].strip()
    return text[:800]


def _coerce_string_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    result: List[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            result.append(item.strip())
    return result


def _coerce_analogies(value: Any) -> List[Dict[str, str]]:
    if not isinstance(value, list):
        return []
    pairs: List[Dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        left = str(item.get("left", "")).strip()
        right = str(item.get("right", "")).strip()
        if left and right:
            pairs.append({"left": left, "right": right})
    return pairs


def _normalize_aliases(raw: Dict[str, Any], diagram_type: str) -> Dict[str, Any]:
    data = dict(raw)
    if diagram_type == "double_bubble_map":
        if "left_topic" in data and "left" not in data:
            data["left"] = data.pop("left_topic")
        if "right_topic" in data and "right" not in data:
            data["right"] = data.pop("right_topic")
    if diagram_type == "circle_map" and "contexts" in data and "context" not in data:
        data["context"] = data.pop("contexts")
    if diagram_type == "brace_map" and "topic" in data and "whole" not in data:
        data["whole"] = data.pop("topic")
    if diagram_type == "flow_map" and "topic" in data and "title" not in data:
        data["title"] = data.pop("topic")
    if diagram_type == "multi_flow_map" and "topic" in data and "event" not in data:
        data["event"] = data.pop("topic")
    return data


def _extract_central(data: Dict[str, Any], diagram_type: str, fallback: str) -> str:
    if diagram_type == "double_bubble_map":
        left = str(data.get("left", "")).strip()
        right = str(data.get("right", "")).strip()
        if left and right:
            return left
        if left:
            return left
        if right:
            return right
    central_key = _CENTRAL_FIELD_BY_TYPE.get(diagram_type, "topic")
    value = data.get(central_key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    for key in ("topic", "title", "whole", "event"):
        alt = data.get(key)
        if isinstance(alt, str) and alt.strip():
            return alt.strip()
    return fallback.strip()


def _has_fixed_nodes(data: Dict[str, Any], diagram_type: str) -> bool:
    allowed = _FIXED_NODE_KEYS_BY_TYPE.get(diagram_type, frozenset())
    for key in allowed:
        if key not in data:
            continue
        value = data[key]
        if key in _LIST_KEYS and _coerce_string_list(value):
            return True
        if key == "analogies" and _coerce_analogies(value):
            return True
        if key == "dimension" and isinstance(value, str) and value.strip():
            return True
    if diagram_type == "double_bubble_map":
        left = str(data.get("left", "")).strip()
        right = str(data.get("right", "")).strip()
        if left and right:
            return True
    return False


def _collect_fixed_nodes(data: Dict[str, Any], diagram_type: str) -> Dict[str, Any]:
    allowed = _FIXED_NODE_KEYS_BY_TYPE.get(diagram_type, frozenset())
    fixed: Dict[str, Any] = {}
    for key in allowed:
        if key not in data:
            continue
        value = data[key]
        if key in _LIST_KEYS:
            items = _coerce_string_list(value)
            if items:
                fixed[key] = items
        elif key == "analogies":
            pairs = _coerce_analogies(value)
            if pairs:
                fixed[key] = pairs
        elif key == "dimension" and isinstance(value, str) and value.strip():
            fixed[key] = value.strip()
    if diagram_type == "double_bubble_map":
        left = str(data.get("left", "")).strip()
        right = str(data.get("right", "")).strip()
        if left:
            fixed["left"] = left
        if right:
            fixed["right"] = right
    return fixed


def parse_requirements_for_type(
    diagram_type: str,
    raw_json: Any,
    fallback_prompt: str = "",
) -> ParsedRequirements:
    """Validate and normalize LLM requirements JSON for a diagram type."""
    dtype = normalize_diagram_type_for_requirements(diagram_type)
    fallback = (fallback_prompt or "").strip()

    if not isinstance(raw_json, dict):
        return ParsedRequirements(
            structure_mode="free",
            central=fallback,
            diagram_type=dtype,
        )

    data = _normalize_aliases(raw_json, dtype)
    clarity = str(data.get("clarity", "clear")).strip().lower()
    if clarity not in ("clear", "unclear"):
        clarity = "clear"
    constraints = str(data.get("constraints", "") or "").strip()
    central = _extract_central(data, dtype, fallback)

    mode_raw = str(data.get("structure_mode", "free")).strip().lower()
    structure_mode: StructureMode = "fixed" if mode_raw == "fixed" else "free"
    fixed_nodes = _collect_fixed_nodes(data, dtype)

    if structure_mode == "fixed" and not fixed_nodes and not (
        dtype == "double_bubble_map"
        and data.get("left")
        and data.get("right")
    ):
        structure_mode = "free"
        fixed_nodes = {}

    if _has_fixed_nodes(data, dtype):
        structure_mode = "fixed"
        fixed_nodes = _collect_fixed_nodes(data, dtype)

    return ParsedRequirements(
        structure_mode=structure_mode,
        central=central,
        fixed_nodes=fixed_nodes,
        clarity=clarity,
        constraints=constraints,
        diagram_type=dtype,
    )


def build_agent_context(_diagram_type: str, parsed: ParsedRequirements) -> str:
    """Build user-message suffix for fixed structure (Case 2)."""
    if parsed.structure_mode != "fixed" or not parsed.fixed_nodes:
        if parsed.constraints:
            return f"Additional constraints: {parsed.constraints}"
        return ""

    lines: List[str] = ["User-specified structure (use EXACT labels, expand sub-detail only):"]
    for key, value in parsed.fixed_nodes.items():
        if isinstance(value, list):
            if key == "analogies":
                pair_text = ", ".join(f"{p['left']}→{p['right']}" for p in value if isinstance(p, dict))
                lines.append(f"- {key}: {pair_text}")
            else:
                lines.append(f"- {key}: {', '.join(str(v) for v in value)}")
        else:
            lines.append(f"- {key}: {value}")
    if parsed.constraints:
        lines.append(f"Constraints: {parsed.constraints}")
    return "\n".join(lines)


def map_to_agent_params(diagram_type: str, parsed: ParsedRequirements) -> AgentRequirementParams:
    """Map parsed requirements to agent kwargs."""
    dtype = normalize_diagram_type_for_requirements(diagram_type)
    params = AgentRequirementParams(
        structure_mode=parsed.structure_mode,
        fixed_nodes=dict(parsed.fixed_nodes),
        constraints=parsed.constraints,
        agent_user_message_suffix=build_agent_context(dtype, parsed),
    )

    dimension = parsed.fixed_nodes.get("dimension")
    if isinstance(dimension, str) and dimension.strip():
        params.fixed_dimension = dimension.strip()

    analogies = parsed.fixed_nodes.get("analogies")
    if isinstance(analogies, list) and analogies:
        params.existing_analogies = analogies

    if dtype in ("tree_map", "brace_map", "bridge_map"):
        central_empty = not parsed.central.strip()
        if params.fixed_dimension and central_empty:
            params.dimension_only_mode = True

    return params


def merge_agent_params(
    api_kwargs: Dict[str, Any],
    extracted: AgentRequirementParams,
) -> AgentRequirementParams:
    """Merge API-provided structure with NL-extracted requirements; API wins."""
    merged = AgentRequirementParams(
        structure_mode=extracted.structure_mode,
        fixed_nodes=dict(extracted.fixed_nodes),
        constraints=extracted.constraints,
        agent_user_message_suffix=extracted.agent_user_message_suffix,
    )

    api_fixed = api_kwargs.get("fixed_dimension")
    if isinstance(api_fixed, str) and api_fixed.strip():
        merged.fixed_dimension = api_fixed.strip()

    api_dim_only = api_kwargs.get("dimension_only_mode")
    if api_dim_only is True:
        merged.dimension_only_mode = True

    api_analogies = api_kwargs.get("existing_analogies")
    if isinstance(api_analogies, list) and api_analogies:
        merged.existing_analogies = api_analogies
        merged.structure_mode = "fixed"

    api_dim_pref = api_kwargs.get("dimension_preference")
    if not merged.fixed_dimension and isinstance(api_dim_pref, str) and api_dim_pref.strip():
        merged.fixed_dimension = api_dim_pref.strip()

    return merged


def build_generation_user_message(
    central: str,
    params: AgentRequirementParams,
    language: str,
    rag_context_block: str = "",
) -> str:
    """Build agent user message from central topic and requirement params."""
    parts: List[str] = []
    if central.strip():
        if is_chinese_prompt_shell_language(language):
            parts.append(f"主题/描述：{central.strip()}")
        else:
            parts.append(f"Topic/description: {central.strip()}")
    if params.agent_user_message_suffix.strip():
        parts.append(params.agent_user_message_suffix.strip())
    elif params.constraints.strip():
        label = "额外要求" if is_chinese_prompt_shell_language(language) else "Additional constraints"
        parts.append(f"{label}: {params.constraints.strip()}")
    if rag_context_block.strip():
        parts.append(rag_context_block.strip())
    if not parts:
        return central.strip()
    return "\n\n".join(parts)


async def extract_prompt_requirements(
    user_prompt: str,
    diagram_type: str,
    language: str = "zh",
    model: str = "qwen",
    user_id=None,
    organization_id=None,
    request_type: str = "diagram_generation",
    endpoint_path: Optional[str] = None,
    phase_emit=None,
) -> ParsedRequirements:
    """Run LLM requirements extraction after diagram type is known."""
    dtype = normalize_diagram_type_for_requirements(diagram_type)
    fallback = (user_prompt or "").strip()

    if phase_emit is not None:
        await phase_emit("requirements")

    try:
        base = get_prompt("prompt_requirements", language, "generation")
        if not base:
            logger.warning("No prompt_requirements template for language %s", language)
            return parse_requirements_for_type(dtype, {}, fallback)

        schema_block = get_requirements_schema(dtype, language)
        topic_rules = _topic_extraction_rules(language)
        prompt = base.format(
            user_prompt=user_prompt,
            diagram_type=dtype,
            requirements_schema=schema_block,
            topic_extraction_rules=topic_rules,
        )

        response = await llm_service.chat(
            prompt=prompt,
            model=model,
            max_tokens=800,
            temperature=0.3,
            user_id=user_id,
            organization_id=organization_id,
            request_type=request_type,
            endpoint_path=endpoint_path,
        )

        raw = extract_json_from_response(str(response))
        if not raw:
            logger.warning("Requirements extraction returned non-JSON; using fallback")
            return parse_requirements_for_type(dtype, {}, fallback)

        return parse_requirements_for_type(dtype, raw, fallback)

    except LLM_PIPELINE_ERRORS as exc:
        logger.error("Requirements extraction failed: %s", exc)
        return parse_requirements_for_type(dtype, {}, fallback)
