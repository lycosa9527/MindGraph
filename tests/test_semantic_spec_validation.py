"""Tests for agent-authored semantic diagram spec validation."""

from __future__ import annotations

from typing import Any, Dict, List, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from models.common import DiagramType
from models.requests.requests_diagram import DiagramCreateRequest, ExportPNGRequest
from routers.api.diagrams import create_diagram
from routers.api.png_export import export_png
from services.diagram.semantic_spec_validation import (
    ensure_valid_semantic_spec,
    invalid_diagram_spec_detail,
    validate_semantic_spec,
)


def _structured_spec_detail(detail: object) -> Dict[str, Any]:
    """Narrow HTTPException.detail to the invalid_diagram_spec payload."""
    assert isinstance(detail, dict)
    return cast(Dict[str, Any], detail)


_MINIMAL_VALID: Dict[str, Dict[str, Any]] = {
    "circle_map": {
        "topic": "Photosynthesis",
        "context": ["sun", "water", "CO2"],
    },
    "bubble_map": {
        "topic": "Lion",
        "attributes": ["fierce", "mane"],
    },
    "double_bubble_map": {
        "left": "Cat",
        "right": "Dog",
        "similarities": ["pets"],
        "left_differences": ["meows"],
        "right_differences": ["barks"],
    },
    "tree_map": {
        "topic": "Animals",
        "children": [
            {
                "text": "Mammals",
                "children": [{"text": "Dog", "children": []}],
            }
        ],
    },
    "brace_map": {
        "whole": "Plant",
        "parts": [{"name": "Root", "subparts": [{"name": "Hair"}]}],
    },
    "flow_map": {
        "title": "Brew coffee",
        "steps": ["Grind", "Brew"],
    },
    "multi_flow_map": {
        "event": "Rain",
        "causes": ["Clouds"],
        "effects": ["Wet ground"],
    },
    "bridge_map": {
        "relating_factor": "as",
        "analogies": [{"left": "bird", "right": "plane"}],
    },
    "mind_map": {
        "topic": "Central",
        "children": [{"id": "branch_0", "label": "Idea", "children": []}],
    },
    "concept_map": {
        "topic": "What is water?",
        "concepts": ["H2O"],
        "relationships": [{"from": "What is water?", "to": "H2O", "label": "is"}],
        "focus_question": "What is water?",
    },
}


@pytest.mark.parametrize("diagram_type", sorted(_MINIMAL_VALID.keys()))
def test_minimal_valid_semantic_specs(diagram_type: str) -> None:
    """Each diagram type accepts a minimal semantic fixture."""
    ok, issues, normalized = validate_semantic_spec(
        diagram_type,
        _MINIMAL_VALID[diagram_type],
    )
    assert ok, issues
    assert not issues
    assert normalized == diagram_type


def test_mindmap_alias_normalizes() -> None:
    """mindmap alias validates as mind_map."""
    ok, issues, normalized = validate_semantic_spec(
        "mindmap",
        _MINIMAL_VALID["mind_map"],
    )
    assert ok, issues
    assert normalized == "mind_map"


def test_canvas_persist_spec_passthrough() -> None:
    """Editor canvas specs with nodes skip semantic field rules."""
    ok, issues, normalized = validate_semantic_spec(
        "bubble_map",
        {
            "type": "bubble_map",
            "nodes": [{"id": "n1", "data": {"label": "x"}}],
            "connections": [],
        },
    )
    assert ok
    assert not issues
    assert normalized == "bubble_map"


def test_bubble_map_missing_attributes() -> None:
    """Missing attributes yields a clear issue."""
    ok, issues, _normalized = validate_semantic_spec(
        "bubble_map",
        {"topic": "Lion"},
    )
    assert not ok
    assert any("attributes" in item for item in issues)


def test_bubble_map_attributes_wrong_type() -> None:
    """Non-list attributes yields a clear issue."""
    ok, issues, _normalized = validate_semantic_spec(
        "bubble_map",
        {"topic": "Lion", "attributes": "fierce"},
    )
    assert not ok
    assert any("array of strings" in item for item in issues)


def test_children_require_text_or_label() -> None:
    """Tree/mind children without text/label fail."""
    ok, issues, _normalized = validate_semantic_spec(
        "mind_map",
        {"topic": "Central", "children": [{"id": "x"}]},
    )
    assert not ok
    assert any("text or label" in item for item in issues)


def test_unknown_diagram_type() -> None:
    """Unknown diagram_type fails with an explicit issue."""
    ok, issues, normalized = validate_semantic_spec(
        "foo_map",
        {"topic": "x"},
    )
    assert not ok
    assert normalized == "foo_map"
    assert any("Unknown diagram_type" in item for item in issues)


def test_spec_must_be_object() -> None:
    """Non-dict specs are rejected."""
    ok, issues, _normalized = validate_semantic_spec("bubble_map", ["not", "object"])
    assert not ok
    assert any("JSON object" in item for item in issues)


def test_brace_map_accepts_topic_alias() -> None:
    """brace_map accepts topic as whole alias."""
    ok, issues, _normalized = validate_semantic_spec(
        "brace_map",
        {"topic": "Plant", "parts": [{"name": "Leaf"}]},
    )
    assert ok, issues


def test_concept_map_allows_empty_concepts() -> None:
    """Blank concept maps with empty arrays are valid."""
    ok, issues, _normalized = validate_semantic_spec(
        "concept_map",
        {
            "topic": "Focus?",
            "concepts": [],
            "relationships": [],
            "focus_question": "Focus?",
        },
    )
    assert ok, issues


def test_ensure_valid_raises_structured_400() -> None:
    """ensure_valid_semantic_spec raises HTTP 400 with stable detail."""
    with pytest.raises(HTTPException) as exc_info:
        ensure_valid_semantic_spec("bubble_map", {"topic": "Lion"})
    assert exc_info.value.status_code == 400
    detail = _structured_spec_detail(exc_info.value.detail)
    assert detail["error"] == "invalid_diagram_spec"
    assert detail["diagram_type"] == "bubble_map"
    issues = cast(List[str], detail["issues"])
    assert issues
    assert detail == invalid_diagram_spec_detail(
        str(detail["diagram_type"]),
        issues,
    )


def test_ensure_valid_returns_normalized_type() -> None:
    """Valid specs return the normalized diagram type."""
    normalized = ensure_valid_semantic_spec(
        "mindmap",
        _MINIMAL_VALID["mind_map"],
    )
    assert normalized == "mind_map"


@pytest.mark.asyncio
async def test_create_diagram_returns_structured_400() -> None:
    """POST /api/diagrams rejects bad semantic specs before save."""
    req = DiagramCreateRequest(
        title="Bad bubble",
        diagram_type="bubble_map",
        spec={"topic": "Lion"},
        language="en",
        thumbnail=None,
    )
    request = MagicMock()
    user = MagicMock()
    user.id = 1

    with (
        patch(
            "routers.api.diagrams.get_rate_limit_identifier",
            return_value="user:1",
        ),
        patch(
            "routers.api.diagrams.check_endpoint_rate_limit",
            new=AsyncMock(),
        ),
        patch(
            "routers.api.diagrams.get_diagram_cache",
        ) as cache_factory,
    ):
        with pytest.raises(HTTPException) as exc_info:
            await create_diagram(req, request, user, lang=MagicMock())
    assert exc_info.value.status_code == 400
    detail = _structured_spec_detail(exc_info.value.detail)
    assert detail["error"] == "invalid_diagram_spec"
    issues = cast(List[str], detail["issues"])
    assert any("attributes" in item for item in issues)
    cache_factory.assert_not_called()


@pytest.mark.asyncio
async def test_export_png_returns_structured_400() -> None:
    """POST /api/export_png rejects bad semantic specs before render."""
    req = ExportPNGRequest(
        diagram_data={"topic": "Lion"},
        diagram_type=DiagramType.BUBBLE_MAP,
        width=1200,
        height=800,
        scale=2,
    )
    request = MagicMock()
    request.headers = {}

    with (
        patch(
            "routers.api.png_export.get_rate_limit_identifier",
            return_value="user:1",
        ),
        patch(
            "routers.api.png_export.check_endpoint_rate_limit",
            new=AsyncMock(),
        ),
        patch(
            "routers.api.png_export.capture_diagram_screenshot",
            new=AsyncMock(),
        ) as capture,
    ):
        with pytest.raises(HTTPException) as exc_info:
            await export_png(req, request, x_language="en", current_user=None)
    assert exc_info.value.status_code == 400
    detail = _structured_spec_detail(exc_info.value.detail)
    assert detail["error"] == "invalid_diagram_spec"
    capture.assert_not_called()
