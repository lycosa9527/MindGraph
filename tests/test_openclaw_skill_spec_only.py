"""OpenClaw skill must stay spec-only (MindGraph is the pen)."""

from __future__ import annotations

from pathlib import Path

_SKILL = Path(__file__).resolve().parents[1] / "openclaw" / "skills" / "mindgraph" / "SKILL.md"

_BLOCKED_GENERATE_ROUTES = (
    "/api/generate_graph",
    "/api/generate_graph/stream",
    "/api/generate_dingtalk",
    "/api/web_content_mindmap_png",
)


def test_skill_forbids_prompt_generate_routes() -> None:
    """Skill tells the agent never to call prompt-to-diagram APIs."""
    text = _SKILL.read_text(encoding="utf-8")
    assert "Never call" in text
    for route in _BLOCKED_GENERATE_ROUTES:
        assert route in text
    assert "POST /api/generate_graph" not in text.split("## A.")[-1].split("## B.")[0]


def test_skill_has_no_native_prompt_section() -> None:
    """Removed generate_graph fallback must stay gone."""
    text = _SKILL.read_text(encoding="utf-8")
    assert "## B. Native prompt" not in text
    assert "generate_graph only" not in text
    assert "POST {MINDGRAPH_BASE_URL}/api/generate_graph" not in text


def test_skill_documents_spec_save_and_png() -> None:
    """Pen path is save then PNG."""
    text = _SKILL.read_text(encoding="utf-8")
    assert "POST {MINDGRAPH_BASE_URL}/api/diagrams" in text
    assert "GET {MINDGRAPH_BASE_URL}/api/diagrams/{id}/png" in text
    assert "invalid_diagram_spec" in text


_PICK_TYPES = (
    "circle_map",
    "bubble_map",
    "double_bubble_map",
    "tree_map",
    "brace_map",
    "flow_map",
    "multi_flow_map",
    "bridge_map",
    "mind_map",
    "concept_map",
)

_LOOKALIKES = (
    "Circle vs bubble",
    "Tree vs brace",
    "Flow vs multi-flow",
    "Double bubble vs bridge",
    "Mind vs concept",
    "Mind vs circle",
)


def test_skill_teaches_when_to_use_each_type() -> None:
    """Picker must cover all ten types, defaults, and lookalike pairs."""
    text = _SKILL.read_text(encoding="utf-8")
    picker = text.split("## Pick `diagram_type`")[1].split("## Auth")[0]
    assert "Topic only" in picker or "unclear" in picker
    assert "`mind_map`" in picker
    for slug in _PICK_TYPES:
        assert f"`{slug}`" in picker
    for pair in _LOOKALIKES:
        assert pair in picker
    assert "Worked picks" in picker


def test_skill_http_errors_are_short_and_actionable() -> None:
    """401/403/429/500 tell the agent to stop or retry the same call, not rewrite spec."""
    text = _SKILL.read_text(encoding="utf-8")
    box = text.split("### HTTP errors")[1].split("## A.")[0]
    assert "**401**" in box
    assert "**403**" in box
    assert "**429**" in box
    assert "**500**" in box
    assert "Never echo the token" in box
    assert "generate API" in box
    assert "JWT token required" not in text
