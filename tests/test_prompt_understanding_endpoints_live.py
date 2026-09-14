"""LIVE_LLM: HTTP generate_graph / generate_dingtalk and Kitty agent loop.

Run (WSL + conda):
  LIVE_LLM=1 python -m pytest tests/test_prompt_understanding_endpoints_live.py -q --tb=short
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from agents.core.prompt_understanding import prepare_generation_prompt
from clients.llm.http_client_manager import reset_httpx_clients_for_tests
from routers.api import diagram_generation, png_export
from services.diagram.dify_user_resolve import DiagramSaveIdentity
from services.kitty.agent_loop.fresh_diagram_generate import resolve_fresh_diagram_commands
from services.kitty.agent_loop.loop import run_typed_agent_loop
from services.kitty.routing.outcomes import RouteOutcome
from services.kitty.session.ops import create_voice_session
from services.kitty.session.runtime_state import voice_sessions
from services.llm import llm_service
from services.redis.redis_client import init_redis_sync
from tests.smoke.mindmap_smoke_helpers import live_llm_enabled, mindmap_smoke_helpers_load_dotenv
from tests.typing_helpers import mock_await_args
from tests.test_prompt_understanding_methods_live import (
    CASES,
    LiveCase,
    _assert_prepared,
    _assert_spec,
    _fresh_kitty_context,
    _retry,
)
from utils.auth import get_current_user_or_api_key

pytestmark = pytest.mark.integration

_PHOTO_SHEET = LiveCase(
    "photo_sheet_primary",
    "光合作用半成品，小学水平",
    "zh",
    ("光合", "光", "植物"),
    "primary",
    True,
)
ENDPOINT_CASES: tuple[LiveCase, ...] = CASES + (_PHOTO_SHEET,)


@pytest.fixture(scope="module", autouse=True)
def _load_repo_dotenv() -> None:
    """Load ``.env`` without bash-sourcing comments."""
    mindmap_smoke_helpers_load_dotenv(Path(__file__).resolve().parents[1] / ".env")


@pytest.fixture(scope="module")
def _live_llm_ready():
    """Initialize Redis + LLM once."""
    if not live_llm_enabled():
        pytest.skip("Set LIVE_LLM=1 and QWEN_API_KEY to run live endpoint tests")
    init_redis_sync()
    llm_service.initialize()
    yield
    reset_httpx_clients_for_tests()


@pytest.fixture(autouse=True)
def _reset_httpx_per_test():
    """Avoid httpx clients bound to a previous pytest event loop."""
    reset_httpx_clients_for_tests()
    yield
    reset_httpx_clients_for_tests()


def _asgi_app() -> FastAPI:
    app = FastAPI()
    app.include_router(diagram_generation.router, prefix="/api")
    app.include_router(png_export.router, prefix="/api")

    async def _anon() -> None:
        return None

    app.dependency_overrides[get_current_user_or_api_key] = _anon
    return app


def _rls_cm() -> MagicMock:
    session_cm = MagicMock()
    session_cm.__aenter__ = AsyncMock(return_value=MagicMock())
    session_cm.__aexit__ = AsyncMock(return_value=None)
    return session_cm


@contextmanager
def _dingtalk_infra(captured: dict[str, Any]) -> Iterator[None]:
    """Keep the real LLM path; stub Playwright, RLS, and temp-file IO."""

    async def _shot(*, diagram_data: dict[str, Any], diagram_type: str, **_kwargs: object) -> bytes:
        captured["spec"] = diagram_data
        captured["diagram_type"] = diagram_type
        return b"\x89PNG\r\n\x1a\nfake"

    identity = DiagramSaveIdentity(user_id=None, organization_id=None, dify_user_key="")
    with (
        patch.object(png_export, "actor_rls_session", return_value=_rls_cm()),
        patch.object(png_export, "system_rls_session", return_value=_rls_cm()),
        patch.object(png_export, "resolve_diagram_save_identity", new=AsyncMock(return_value=identity)),
        patch.object(png_export, "capture_diagram_screenshot", new=AsyncMock(side_effect=_shot)),
        patch.object(png_export, "try_save_diagram_to_library", new=AsyncMock(return_value=None)),
        patch.object(png_export, "store_generation_preview_outcome", new=AsyncMock(return_value=True)),
        patch.object(png_export, "persist_dingtalk_temp_png", new=AsyncMock()),
        patch.object(png_export, "build_public_temp_image_url", return_value="https://x/t.png"),
        patch.object(png_export, "generate_signed_url", return_value="/temp_images/x.png?sig=1"),
        patch.object(png_export, "schedule_module_activity"),
        patch.object(png_export, "schedule_user_usage_activity"),
        patch.object(png_export, "temp_images_signed_ttl", return_value=86400),
    ):
        yield


def _http() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=_asgi_app()), base_url="http://test", timeout=180.0)


def _assert_sheet_topic_clean(spec: dict[str, Any]) -> None:
    topic = spec.get("topic") or spec.get("title") or spec.get("whole") or spec.get("event")
    if isinstance(topic, str):
        assert "半成品" not in topic
        assert "学习单" not in topic


async def _post_generate_graph(case: LiveCase, *, kitty: bool) -> dict[str, Any]:
    body: dict[str, Any] = {"prompt": case.prompt, "language": case.language}
    if kitty:
        understood = prepare_generation_prompt(case.prompt, case.language)
        commands = resolve_fresh_diagram_commands(
            case.prompt,
            _fresh_kitty_context(),
            case.language,
        )
        assert commands is not None
        complete = next(item for item in commands if item.get("action") == "auto_complete")
        topic = str(complete.get("topic") or "").strip()
        prompt = f"{topic} 半成品" if complete.get("is_learning_sheet") is True else topic
        body = {
            "prompt": prompt,
            "language": case.language,
            "diagram_type": "mind_map",
            "request_type": "autocomplete",
        }
        if understood.generation_instructions:
            body["generation_instructions"] = understood.generation_instructions
    async with _http() as client:
        response = await client.post("/api/generate_graph", json=body)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload.get("success") is True, payload.get("error")
    return payload


@pytest.mark.usefixtures("_live_llm_ready")
@pytest.mark.asyncio
@pytest.mark.parametrize("case", ENDPOINT_CASES, ids=[item.case_id for item in ENDPOINT_CASES])
async def test_live_http_generate_graph(case: LiveCase) -> None:
    """Landing box: POST /api/generate_graph."""
    _assert_prepared(case)
    payload = await _retry(lambda: _post_generate_graph(case, kitty=False))
    spec = payload.get("spec")
    assert isinstance(spec, dict)
    _assert_spec(case, spec, learning_sheet=case.learning_sheet)
    assert bool(payload.get("is_learning_sheet")) is case.learning_sheet
    if case.learning_sheet:
        assert payload.get("hidden_node_percentage") == 0.2
        assert spec.get("hidden_node_percentage") == 0.2
        _assert_sheet_topic_clean(spec)


@pytest.mark.usefixtures("_live_llm_ready")
@pytest.mark.asyncio
@pytest.mark.parametrize("case", ENDPOINT_CASES, ids=[item.case_id for item in ENDPOINT_CASES])
async def test_live_http_generate_dingtalk(case: LiveCase) -> None:
    """DingTalk: POST /api/generate_dingtalk (live LLM, stub Playwright IO)."""
    _assert_prepared(case)
    captured: dict[str, Any] = {}

    async def _call() -> dict[str, Any]:
        with _dingtalk_infra(captured):
            async with _http() as client:
                response = await client.post(
                    "/api/generate_dingtalk",
                    json={"prompt": case.prompt, "language": case.language},
                )
        assert response.status_code == 200, response.text
        assert response.text.startswith("![](")
        spec = captured.get("spec")
        assert isinstance(spec, dict)
        return spec

    spec = await _retry(_call)
    _assert_spec(case, spec, learning_sheet=case.learning_sheet)
    if case.learning_sheet:
        assert spec.get("hidden_node_percentage") == 0.2
        _assert_sheet_topic_clean(spec)


@pytest.mark.usefixtures("_live_llm_ready")
@pytest.mark.asyncio
@pytest.mark.parametrize("case", ENDPOINT_CASES, ids=[item.case_id for item in ENDPOINT_CASES])
async def test_live_kitty_agent_then_generate_graph(case: LiveCase) -> None:
    """Kitty agent loop on a fresh map, then canvas POST /api/generate_graph."""
    _assert_prepared(case)
    context = _fresh_kitty_context()
    context["interaction_language"] = case.language
    ws = MagicMock()
    vid = create_voice_session(
        user_id="1",
        diagram_session_id=f"scope-ep-{case.case_id}",
        diagram_type="mind_map",
    )
    voice_sessions[vid]["context"] = context
    ac_sent = AsyncMock(return_value=True)
    pref_sent = AsyncMock(return_value=True)
    try:
        with (
            patch("services.kitty.agent_loop.tools.send_kitty_ws_action", ac_sent),
            patch("services.kitty.agent_loop.preference_tools.send_kitty_ws_action", pref_sent),
            patch("services.kitty.agent_loop.loop.emit_user_ack", new=AsyncMock(return_value=True)),
            patch("services.kitty.agent_loop.tools.emit_user_ack", new=AsyncMock(return_value=True)),
            patch("services.kitty.agent_loop.preference_tools.emit_user_ack", new=AsyncMock(return_value=True)),
            patch("services.kitty.agent_loop.tools.fanout_voice_command_from_session", new=AsyncMock()),
            patch(
                "services.kitty.agent_loop.preference_tools.fanout_voice_command_from_session",
                new=AsyncMock(),
            ),
            patch("services.kitty.agent_loop.loop.load_kitty_live_context", new=AsyncMock(return_value=None)),
            patch(
                "services.kitty.agent_loop.loop.throttled_refresh_voice_context_from_library",
                new=AsyncMock(),
            ),
            patch(
                "services.kitty.agent_loop.loop.live_spec_newer_than_library",
                new=AsyncMock(return_value=True),
            ),
            patch("services.kitty.agent_loop.loop.fanout_voice_phase_from_session", new=AsyncMock()),
        ):
            result = await run_typed_agent_loop(ws, vid, case.prompt, dict(context))
        assert result.outcome == RouteOutcome.EXECUTED
        assert result.reason == "fresh_diagram"
        assert result.action == "auto_complete"
        assert ac_sent.await_count == 1
        params = mock_await_args(ac_sent)[2]["params"]
        assert params.get("topic")
        if case.learning_sheet:
            assert params.get("is_learning_sheet") is True
        else:
            assert "is_learning_sheet" not in params
        if case.level not in {"general"}:
            assert pref_sent.await_count == 1
            assert mock_await_args(pref_sent)[2]["params"]["level"] == case.level
        payload = await _retry(lambda: _post_generate_graph(case, kitty=True))
        spec = payload.get("spec")
        assert isinstance(spec, dict)
        _assert_spec(case, spec, learning_sheet=case.learning_sheet)
        assert bool(payload.get("is_learning_sheet")) is case.learning_sheet
        if case.learning_sheet:
            assert payload.get("hidden_node_percentage") == 0.2
            _assert_sheet_topic_clean(spec)
    finally:
        voice_sessions.pop(vid, None)
