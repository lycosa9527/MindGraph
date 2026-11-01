"""LIVE_LLM: each seminar summary range and the minutes HTTP route.

The dialog offers 全部消息, 自上次纪要之后, 已设为精华的消息, and 自选消息.
Each range posts a different transcript to the same route. This calls
qwen3.8-flash and checks the reply stays inside that transcript.

Run (WSL + conda):

  LIVE_LLM=1 python -m pytest tests/test_mindmate_seminar_minutes_live.py -q --tb=short -s
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers.api.mindmate_seminar_routes import router as seminar_router
from services.infrastructure.utils.client_manager import client_manager
from tests.smoke.mindmap_smoke_helpers import live_llm_enabled, mindmap_smoke_helpers_load_dotenv
from utils.auth import get_current_user

pytestmark = pytest.mark.integration

app = FastAPI()
app.include_router(seminar_router, prefix="/api")

_KEYS = ("goals", "consensus", "open", "materials", "tasks", "quotes")
_STATUSES = {"met", "partial", "open"}


def _user() -> SimpleNamespace:
    user = SimpleNamespace()
    user.id = 7
    user.organization_id = None
    return user


def _parse_minutes(raw: str) -> dict[str, Any]:
    text = raw.strip()
    fenced = text.find("```")
    fence_end = text.rfind("```")
    if 0 <= fenced < fence_end:
        inner = text[fenced + 3 :]
        inner = inner.split("\n", 1)[-1]
        text = inner.rsplit("```", 1)[0]
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise AssertionError(f"minutes reply was not JSON: {raw[:400]}")
    parsed = json.loads(text[start : end + 1])
    if not isinstance(parsed, dict):
        raise AssertionError("minutes reply was not an object")
    return parsed


def _assert_minutes(parsed: dict[str, Any], keep: tuple[str, ...], drop: tuple[str, ...]) -> None:
    missing = [key for key in _KEYS if key not in parsed]
    assert not missing, parsed
    goals = parsed["goals"]
    assert isinstance(goals, list)
    for row in goals:
        assert isinstance(row, dict)
        assert row.get("status") in _STATUSES
    blob = json.dumps(parsed, ensure_ascii=False)
    for token in keep:
        assert token in blob, blob
    for token in drop:
        assert token not in blob, blob


_CASES = (
    {
        "name": "all",
        "keep": ("青柠导入", "琥珀作业"),
        "drop": (),
        "body": {
            "zh": True,
            "topic": "导入",
            "goals": ["先改青柠导入", "安排琥珀作业"],
            "speakers": "王雅萱（组长）、董长华",
            "observers": "李观摩",
            "files": ["框架.pdf"],
            "quotes": [],
            "transcript": "王雅萱：先改青柠导入。\n\n董长华：琥珀作业下周再交。",
        },
    },
    {
        "name": "since",
        "keep": ("琥珀作业",),
        "drop": ("青柠导入",),
        "body": {
            "zh": True,
            "topic": "导入",
            "goals": ["安排琥珀作业"],
            "speakers": "董长华",
            "observers": "",
            "files": [],
            "quotes": [],
            "transcript": "董长华：上次纪要之后，琥珀作业改到周五。",
        },
    },
    {
        "name": "highlights",
        "keep": ("留白板书",),
        "drop": ("青柠导入", "琥珀作业"),
        "body": {
            "zh": True,
            "topic": "板书",
            "goals": [],
            "speakers": "王雅萱（组长）",
            "observers": "",
            "files": [],
            "quotes": ["王雅萱：留白板书给学生抄"],
            "transcript": "王雅萱：留白板书给学生抄。",
        },
    },
    {
        "name": "part",
        "keep": ("框架图纸",),
        "drop": ("青柠导入", "琥珀作业", "留白板书"),
        "body": {
            "zh": True,
            "topic": "材料",
            "goals": [],
            "speakers": "董长华",
            "observers": "",
            "files": ["框架图纸.pdf"],
            "quotes": [],
            "transcript": "董长华：用框架图纸说明这一页的结构。",
        },
    },
    {
        "name": "english",
        "keep": ("linden opening",),
        "drop": ("青柠导入",),
        "body": {
            "zh": False,
            "topic": "Opening",
            "goals": ["Shorten the linden opening"],
            "speakers": "Wang",
            "observers": "",
            "files": [],
            "quotes": [],
            "transcript": "Wang: Shorten the linden opening before Friday.",
        },
    },
)


@pytest.fixture(scope="module", autouse=True)
def _boot_live_llm() -> None:
    """Load .env and the DashScope client. Skip the file when live calls are off."""
    mindmap_smoke_helpers_load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    if not live_llm_enabled():
        pytest.skip("Set LIVE_LLM=1 and QWEN_API_KEY to call qwen3.8-flash")
    client_manager.initialize()


@pytest.fixture(name="client")
def fixture_client() -> Iterator[TestClient]:
    """Minutes route with seminar access stubbed and the real model left in place."""
    app.dependency_overrides[get_current_user] = _user
    patches = (
        patch(
            "routers.api.mindmate_seminar_routes.user_has_feature_access",
            new=AsyncMock(return_value=True),
        ),
        patch("routers.api.mindmate_seminar_minutes._require_collab_tier", new=AsyncMock()),
        patch("routers.api.mindmate_seminar_minutes.check_endpoint_rate_limit", new=AsyncMock()),
        patch("routers.api.mindmate_seminar_minutes._writable_session", new=AsyncMock()),
        patch("services.llm.assert_llm_usage_budget", new=AsyncMock()),
        patch("services.llm.thinking_coins_apply_to_user", new=AsyncMock(return_value=False)),
        patch(
            "services.auth.thinking_coin.usage_wire.thinking_coins_apply_to_user",
            new=AsyncMock(return_value=False),
        ),
    )
    for item in patches:
        item.start()
    try:
        with TestClient(app) as test_client:
            test_client.timeout = 120.0
            yield test_client
    finally:
        for item in reversed(patches):
            item.stop()
        app.dependency_overrides.clear()


@pytest.mark.parametrize("case", _CASES, ids=[item["name"] for item in _CASES])
def test_minutes_route_summarizes_each_range(client: TestClient, case: dict[str, Any]) -> None:
    """POST /api/mindmate/seminar/{session_id}/minutes for one dialog range."""
    response = client.post("/api/mindmate/seminar/room-1/minutes", json=case["body"])
    assert response.status_code == 200, response.text
    payload = response.json()
    assert isinstance(payload.get("text"), str) and payload["text"].strip()
    parsed = _parse_minutes(payload["text"])
    _assert_minutes(parsed, case["keep"], case["drop"])
