"""Every diagram type starts AI brainstorm on the renamed route and returns a node."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Generator
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from agents.ai_brainstorm.brace_map import get_brace_map_brainstorm_generator
from agents.ai_brainstorm.bridge_map import get_bridge_map_brainstorm_generator
from agents.ai_brainstorm.bubble_map import get_bubble_map_brainstorm_generator
from agents.ai_brainstorm.circle_map import get_circle_map_brainstorm_generator
from agents.ai_brainstorm.concept_map import get_concept_map_brainstorm_generator
from agents.ai_brainstorm.double_bubble import get_double_bubble_brainstorm_generator
from agents.ai_brainstorm.flow_map import get_flow_map_brainstorm_generator
from agents.ai_brainstorm.mindmap import get_mindmap_brainstorm_generator
from agents.ai_brainstorm.multi_flow import get_multi_flow_brainstorm_generator
from agents.ai_brainstorm.tree_map import get_tree_map_brainstorm_generator
from config.database import get_async_db
from routers.ai_brainstorm import router
from services.llm import llm_service
from utils.auth import get_current_user

_NODE_TEXT = "电场强度"

# First-open payloads match the canvas. The prompt marker is unique to that generator.
_CASES: tuple[dict[str, Any], ...] = (
    {
        "diagram_type": "circle_map",
        "diagram_data": {"center": {"text": "水循环"}, "topic": "水循环"},
        "marker": "圆圈图",
    },
    {
        "diagram_type": "bubble_map",
        "diagram_data": {"center": {"text": "太阳"}, "topic": "太阳"},
        "marker": "气泡图",
    },
    {
        "diagram_type": "double_bubble_map",
        "diagram_data": {"left": "电场", "right": "磁场"},
        "mode": "both",
        "marker": "双气泡图",
    },
    {
        "diagram_type": "multi_flow_map",
        "diagram_data": {"event": "下雨"},
        "mode": "both",
        "marker": "复流程图",
    },
    {
        "diagram_type": "tree_map",
        "diagram_data": {"topic": "动物"},
        "stage": "dimensions",
        "marker": "分类维度",
    },
    {
        "diagram_type": "brace_map",
        "diagram_data": {"whole": "自行车"},
        "stage": "dimensions",
        "marker": "括号图",
    },
    {
        "diagram_type": "flow_map",
        "diagram_data": {"title": "泡茶"},
        "stage": "steps",
        "marker": "流程图",
    },
    {
        "diagram_type": "bridge_map",
        "diagram_data": {"dimension": ""},
        "stage": "dimensions",
        "marker": "桥形图",
    },
    {
        "diagram_type": "mindmap",
        "diagram_data": {"topic": "光合作用"},
        "stage": "branches",
        "marker": "思维导图",
    },
    {
        "diagram_type": "concept_map",
        "diagram_data": {"topic": "生态系统", "focus_question": "生态系统如何运转"},
        "mode": "topic",
        "marker": "概念图",
    },
)

_GETTERS = {
    "circle_map": get_circle_map_brainstorm_generator,
    "bubble_map": get_bubble_map_brainstorm_generator,
    "double_bubble_map": get_double_bubble_brainstorm_generator,
    "multi_flow_map": get_multi_flow_brainstorm_generator,
    "tree_map": get_tree_map_brainstorm_generator,
    "brace_map": get_brace_map_brainstorm_generator,
    "flow_map": get_flow_map_brainstorm_generator,
    "bridge_map": get_bridge_map_brainstorm_generator,
    "mindmap": get_mindmap_brainstorm_generator,
    "concept_map": get_concept_map_brainstorm_generator,
}

_CLASS_NAMES = {
    "circle_map": "CircleMapBrainstormGenerator",
    "bubble_map": "BubbleMapBrainstormGenerator",
    "double_bubble_map": "DoubleBubbleBrainstormGenerator",
    "multi_flow_map": "MultiFlowBrainstormGenerator",
    "tree_map": "TreeMapBrainstormGenerator",
    "brace_map": "BraceMapBrainstormGenerator",
    "flow_map": "FlowMapBrainstormGenerator",
    "bridge_map": "BridgeMapBrainstormGenerator",
    "mindmap": "MindMapBrainstormGenerator",
    "concept_map": "ConceptMapBrainstormGenerator",
}

app = FastAPI()
app.include_router(router)


def _user() -> Any:
    return type("User", (), {"id": 1, "organization_id": 1, "role": "student"})()


async def _db() -> AsyncIterator[object]:
    yield object()


@pytest.fixture(name="client")
def fixture_client() -> TestClient:
    """Client bound to the AI brainstorm router only."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def _overrides() -> Generator[None, None, None]:
    app.dependency_overrides[get_current_user] = _user
    app.dependency_overrides[get_async_db] = _db
    yield
    app.dependency_overrides.clear()


def test_old_node_palette_path_is_gone(client: TestClient) -> None:
    """Clients must use /thinking_mode/ai_brainstorm."""
    paths = [getattr(route, "path", "") for route in router.routes]
    assert "/thinking_mode/ai_brainstorm/start" in paths
    assert "/thinking_mode/ai_brainstorm/next_batch" in paths
    assert not any("node_palette" in path for path in paths)
    response = client.post("/thinking_mode/node_palette/start", json={})
    assert response.status_code == 404


@pytest.mark.parametrize("case", _CASES, ids=[str(case["diagram_type"]) for case in _CASES])
def test_start_streams_a_node_for_diagram(case: dict[str, Any], client: TestClient) -> None:
    """Start uses that diagram's generator and streams one node."""
    prompts: list[str] = []

    async def _fake_stream(**kwargs: Any) -> AsyncIterator[dict[str, Any]]:
        prompts.append(str(kwargs.get("prompt", "")))
        yield {"event": "token", "llm": "express", "token": f"{_NODE_TEXT}\n"}
        yield {"event": "complete", "llm": "express", "duration": 0, "token_count": 4}

    with pytest.MonkeyPatch.context() as patch:
        _silence_side_effects(patch)
        patch.setattr(llm_service, "stream_progressive", _fake_stream)
        response = client.post("/thinking_mode/ai_brainstorm/start", json=_payload(case))

    assert response.status_code == 200, response.text
    events = _sse_events(response.text)
    assert any(case["marker"] in prompt for prompt in prompts), prompts[:1]
    nodes = [event for event in events if event.get("event") == "node_generated"]
    assert nodes, events[:4]
    assert any(_NODE_TEXT in str(event.get("node", {}).get("text", "")) for event in nodes)


def test_concept_map_domain_bootstrap(client: TestClient) -> None:
    """Generate Concepts still runs on the concept-map brainstorm route."""

    async def _fake_chat(**kwargs: Any) -> str:
        assert kwargs.get("request_type") == "ai_brainstorm"
        assert "/thinking_mode/ai_brainstorm/start" in str(kwargs.get("endpoint_path", ""))
        assert "生态系统" in str(kwargs.get("prompt", ""))
        return "能量流\n物质循环\n"

    with pytest.MonkeyPatch.context() as patch:
        _silence_side_effects(patch)
        patch.setattr(llm_service, "chat", _fake_chat)
        response = client.post(
            "/thinking_mode/ai_brainstorm/start",
            json={
                "session_id": "audit-concept-bootstrap",
                "diagram_type": "concept_map",
                "diagram_data": {"topic": "生态系统"},
                "language": "zh",
                "mode": "topic",
                "stage_data": {
                    "bootstrap_domains": True,
                    "center_topic": "生态系统",
                    "domain_count": 2,
                },
                "llm_models": ["express"],
            },
        )

    assert response.status_code == 200, response.text
    events = _sse_events(response.text)
    domains = next(event for event in events if event.get("event") == "concept_map_domains")
    assert domains["domains"][:2] == ["能量流", "物质循环"]


@pytest.mark.parametrize("case", _CASES, ids=[f"life-{case['diagram_type']}" for case in _CASES])
def test_next_select_finish_cancel_and_cleanup(case: dict[str, Any], client: TestClient) -> None:
    """Load-more, selection, finish, cancel, and cleanup stay on the brainstorm routes."""
    generator = _GETTERS[case["diagram_type"]]()
    closed: list[tuple[str, str]] = []
    original_end = generator.end_session

    def _end(session_id: str, reason: str = "complete") -> None:
        closed.append((type(generator).__name__, reason))
        original_end(session_id, reason)

    async def _fake_stream(**_kwargs: Any) -> AsyncIterator[dict[str, Any]]:
        yield {"event": "token", "llm": "express", "token": f"{_NODE_TEXT}\n"}
        yield {"event": "complete", "llm": "express", "duration": 0, "token_count": 4}

    session_id = f"life-{case['diagram_type']}"
    with pytest.MonkeyPatch.context() as patch:
        _silence_side_effects(patch)
        patch.setattr(generator, "end_session", _end)
        patch.setattr(llm_service, "stream_progressive", _fake_stream)
        nxt = client.post("/thinking_mode/ai_brainstorm/next_batch", json=_next_payload(case, session_id))
        selected = client.post(
            "/thinking_mode/ai_brainstorm/select_node",
            json={
                "session_id": session_id,
                "node_id": "n1",
                "selected": True,
                "node_text": _NODE_TEXT,
            },
        )
        finished = client.post("/thinking_mode/ai_brainstorm/finish", json=_finish_payload(session_id))
        cancelled = client.post("/thinking_mode/ai_brainstorm/cancel", json=_finish_payload(session_id))
        cleaned = client.post(
            "/thinking_mode/ai_brainstorm/cleanup",
            json={"session_id": session_id, "diagram_type": case["diagram_type"]},
        )

    assert nxt.status_code == 200, nxt.text
    assert any(event.get("event") == "node_generated" for event in _sse_events(nxt.text))
    assert selected.json()["status"] == "logged"
    assert finished.json()["status"] == "closed"
    assert cancelled.json()["status"] == "cancelled"
    assert cleaned.json()["status"] == "session_cleaned"
    assert closed == [(_CLASS_NAMES[case["diagram_type"]], "canvas_exit")]


def _next_payload(case: dict[str, Any], session_id: str) -> dict[str, Any]:
    body = _payload(case)
    body["session_id"] = session_id
    body["center_topic"] = "类比"
    return body


def _finish_payload(session_id: str) -> dict[str, Any]:
    return {
        "session_id": session_id,
        "selected_node_ids": ["n1"],
        "total_nodes_generated": 1,
        "batches_loaded": 1,
    }


def _payload(case: dict[str, Any]) -> dict[str, Any]:
    body: dict[str, Any] = {
        "session_id": f"audit-{case['diagram_type']}",
        "diagram_type": case["diagram_type"],
        "diagram_data": case["diagram_data"],
        "language": "zh",
        "llm_models": ["express"],
    }
    if "mode" in case:
        body["mode"] = case["mode"]
    if "stage" in case:
        body["stage"] = case["stage"]
    return body


def _sse_events(body: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line in body.splitlines():
        if line.startswith("data: "):
            events.append(json.loads(line[len("data: ") :]))
    return events


def _silence_side_effects(patch: pytest.MonkeyPatch) -> None:
    patch.setattr("routers.ai_brainstorm.assert_student_ai_capability", AsyncMock())
    patch.setattr("routers.ai_brainstorm.assert_collab_blocks_canvas_ai", AsyncMock())
    patch.setattr("routers.ai_brainstorm.track_module_activity", AsyncMock())
