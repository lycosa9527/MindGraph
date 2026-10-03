"""Native JSON Schema for auto-complete LLM tasks.

One schema per task. A bilingual diagram spec adds a required ``secondary``
object with the same keys. Single-language auto-complete does not.
"""

from __future__ import annotations

from typing import Any

from prompts.requirements_schemas import normalize_diagram_type_for_requirements

_STRING = {"type": "string"}
_STRING_LIST = {"type": "array", "items": _STRING}


def _object(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


def _enum(values: list[str]) -> dict[str, Any]:
    return {"type": "string", "enum": values}


def as_response_format(name: str, schema: dict[str, Any]) -> dict[str, Any]:
    """Chat-completions envelope used by Qwen and Volcengine Ark."""
    return {
        "type": "json_schema",
        "json_schema": {
            "name": name,
            "strict": True,
            "schema": schema,
        },
    }


def _with_secondary(schema: dict[str, Any]) -> dict[str, Any]:
    """Require a same-shaped second-language object beside the primary fields."""
    secondary = _object(dict(schema["properties"]), list(schema["required"]))
    secondary["description"] = (
        "Same keys, nesting, and array lengths as the parent. Every string is the second language."
    )
    properties = dict(schema["properties"])
    properties["secondary"] = secondary
    required = list(schema["required"]) + ["secondary"]
    return _object(properties, required)


def _leaf(text_key: str) -> dict[str, Any]:
    return _object({text_key: _STRING}, [text_key])


def _branch(text_key: str, child_key: str) -> dict[str, Any]:
    return _object(
        {text_key: _STRING, child_key: {"type": "array", "items": _leaf(text_key)}},
        [text_key, child_key],
    )


_REQUIREMENT_COMMON = {
    "structure_mode": _enum(["free", "fixed"]),
    "clarity": _enum(["clear", "unclear"]),
    "constraints": _STRING,
}
_REQUIREMENT_REQUIRED = ["structure_mode", "clarity", "constraints"]


def _requirements(extra: dict[str, Any], extra_required: list[str]) -> dict[str, Any]:
    properties = dict(_REQUIREMENT_COMMON)
    properties.update(extra)
    return _object(properties, _REQUIREMENT_REQUIRED + extra_required)


def requirements_schema(diagram_type: str) -> dict[str, Any] | None:
    """Schema for stage-2 requirements extraction."""
    dtype = normalize_diagram_type_for_requirements(diagram_type)
    pair = _object({"left": _STRING, "right": _STRING}, ["left", "right"])
    builders = {
        "mind_map": lambda: _requirements({"topic": _STRING, "children": _STRING_LIST}, ["topic", "children"]),
        "bubble_map": lambda: _requirements({"topic": _STRING, "attributes": _STRING_LIST}, ["topic", "attributes"]),
        "circle_map": lambda: _requirements({"topic": _STRING, "context": _STRING_LIST}, ["topic", "context"]),
        "double_bubble_map": lambda: _requirements(
            {
                "left": _STRING,
                "right": _STRING,
                "similarities": _STRING_LIST,
                "left_differences": _STRING_LIST,
                "right_differences": _STRING_LIST,
            },
            ["left", "right", "similarities", "left_differences", "right_differences"],
        ),
        "tree_map": lambda: _requirements(
            {"topic": _STRING, "dimension": _STRING, "children": _STRING_LIST},
            ["topic", "dimension", "children"],
        ),
        "brace_map": lambda: _requirements(
            {"whole": _STRING, "dimension": _STRING, "parts": _STRING_LIST},
            ["whole", "dimension", "parts"],
        ),
        "flow_map": lambda: _requirements({"title": _STRING, "steps": _STRING_LIST}, ["title", "steps"]),
        "multi_flow_map": lambda: _requirements(
            {"event": _STRING, "causes": _STRING_LIST, "effects": _STRING_LIST},
            ["event", "causes", "effects"],
        ),
        "bridge_map": lambda: _requirements(
            {"topic": _STRING, "dimension": _STRING, "analogies": {"type": "array", "items": pair}},
            ["topic", "dimension", "analogies"],
        ),
        "concept_map": lambda: _requirements({"topic": _STRING, "concepts": _STRING_LIST}, ["topic", "concepts"]),
    }
    build = builders.get(dtype)
    if build is None:
        return None
    return build()


def _spec_schema(diagram_type: str) -> dict[str, Any] | None:
    dtype = normalize_diagram_type_for_requirements(diagram_type)
    text_node = _branch("text", "children")
    brace_subpart = _leaf("name")
    brace_part = _object(
        {"name": _STRING, "subparts": {"type": "array", "items": brace_subpart}},
        ["name", "subparts"],
    )
    flow_group = _object({"step": _STRING, "substeps": _STRING_LIST}, ["step", "substeps"])
    analogy = _object({"left": _STRING, "right": _STRING, "id": {"type": "integer"}}, ["left", "right", "id"])
    relationship = _object(
        {"from": _STRING, "to": _STRING, "label": _STRING},
        ["from", "to", "label"],
    )
    specs = {
        "circle_map": _object({"topic": _STRING, "context": _STRING_LIST}, ["topic", "context"]),
        "bubble_map": _object({"topic": _STRING, "attributes": _STRING_LIST}, ["topic", "attributes"]),
        "double_bubble_map": _object(
            {
                "left": _STRING,
                "right": _STRING,
                "similarities": _STRING_LIST,
                "left_differences": _STRING_LIST,
                "right_differences": _STRING_LIST,
            },
            ["left", "right", "similarities", "left_differences", "right_differences"],
        ),
        "tree_map": _object(
            {
                "topic": _STRING,
                "dimension": _STRING,
                "children": {"type": "array", "items": text_node},
                "alternative_dimensions": _STRING_LIST,
            },
            ["topic", "dimension", "children", "alternative_dimensions"],
        ),
        "brace_map": _object(
            {
                "whole": _STRING,
                "dimension": _STRING,
                "parts": {"type": "array", "items": brace_part},
                "alternative_dimensions": _STRING_LIST,
            },
            ["whole", "dimension", "parts", "alternative_dimensions"],
        ),
        "flow_map": _object(
            {
                "title": _STRING,
                "steps": _STRING_LIST,
                "substeps": {"type": "array", "items": flow_group},
            },
            ["title", "steps", "substeps"],
        ),
        "multi_flow_map": _object(
            {"event": _STRING, "causes": _STRING_LIST, "effects": _STRING_LIST},
            ["event", "causes", "effects"],
        ),
        "bridge_map": _object(
            {
                "relating_factor": _STRING,
                "dimension": _STRING,
                "analogies": {"type": "array", "items": analogy},
                "alternative_dimensions": _STRING_LIST,
            },
            ["relating_factor", "dimension", "analogies", "alternative_dimensions"],
        ),
        "mind_map": _object(
            {"topic": _STRING, "children": {"type": "array", "items": text_node}},
            ["topic", "children"],
        ),
        "concept_map": _object(
            {
                "topic": _STRING,
                "concepts": _STRING_LIST,
                "relationships": {"type": "array", "items": relationship},
            },
            ["topic", "concepts", "relationships"],
        ),
    }
    return specs.get(dtype)


def diagram_spec_response_format(diagram_type: str, *, bilingual: bool) -> dict[str, Any] | None:
    """Schema envelope for the diagram body, or None when the type has no schema."""
    schema = _spec_schema(diagram_type)
    if schema is None:
        return None
    dtype = normalize_diagram_type_for_requirements(diagram_type)
    if bilingual:
        schema = _with_secondary(schema)
    return as_response_format(f"{dtype}_spec", schema)


def requirements_response_format(diagram_type: str) -> dict[str, Any] | None:
    """Schema envelope for requirements extraction."""
    schema = requirements_schema(diagram_type)
    if schema is None:
        return None
    dtype = normalize_diagram_type_for_requirements(diagram_type)
    return as_response_format(f"{dtype}_requirements", schema)


def branch_expand_response_format() -> dict[str, Any]:
    """One-level mind map branch expand. Children are labels, not nested maps."""
    child = _leaf("text")
    schema = _object(
        {"topic": _STRING, "children": {"type": "array", "items": child}},
        ["topic", "children"],
    )
    return as_response_format("mind_map_branch_expand", schema)
