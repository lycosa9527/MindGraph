"""LIVE_LLM: each canvas menu model generates a mind map.

Mobile and desktop both POST ``/api/generate_graph`` with ``llm`` set to the
menu id. This hits Express, Qwen Flash, Qwen Max, GLM Flash, and Doubao.

Run (WSL + conda):

  LIVE_LLM=1 python -m pytest tests/test_canvas_menu_llm_live.py -q --tb=short -s
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from clients.llm.http_client_manager import reset_httpx_clients_for_tests
from routers.api import diagram_generation
from services.llm import llm_service
from services.redis.redis_client import init_redis_sync
from tests.smoke.mindmap_smoke_helpers import live_llm_enabled, mindmap_smoke_helpers_load_dotenv
from utils.auth import get_current_user_or_api_key

pytestmark = pytest.mark.integration

CANVAS_MENU_MODELS = (
    "express",
    "qwen3.8-flash",
    "qwen3-max",
    "kimi",
    "doubao21",
)


@pytest.fixture(scope="module", autouse=True)
def _load_repo_dotenv() -> None:
    """Load ``.env`` without bash-sourcing comments."""
    mindmap_smoke_helpers_load_dotenv(Path(__file__).resolve().parents[1] / ".env")


@pytest.fixture(scope="module")
def _live_llm_ready():
    """Initialize Redis and the LLM clients once."""
    if not live_llm_enabled():
        pytest.skip("Set LIVE_LLM=1 and QWEN_API_KEY to run live canvas model tests")
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

    async def _anon() -> None:
        return None

    app.dependency_overrides[get_current_user_or_api_key] = _anon
    return app


def _spec_has_branches(spec: dict[str, Any]) -> bool:
    for key in ("children", "nodes", "branches"):
        value = spec.get(key)
        if isinstance(value, list) and value:
            return True
    topic = spec.get("topic") or spec.get("title")
    return isinstance(topic, str) and bool(topic.strip())


@pytest.mark.usefixtures("_live_llm_ready")
@pytest.mark.asyncio
@pytest.mark.parametrize("model_id", CANVAS_MENU_MODELS)
async def test_canvas_menu_model_generates_mind_map(model_id: str) -> None:
    """The model id the canvas menu sends produces a mind map."""
    body = {
        "prompt": "猫",
        "language": "zh",
        "diagram_type": "mind_map",
        "request_type": "autocomplete",
        "llm": model_id,
    }
    async with AsyncClient(
        transport=ASGITransport(app=_asgi_app()),
        base_url="http://test",
        timeout=180.0,
    ) as client:
        response = await client.post("/api/generate_graph", json=body)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload.get("success") is True, payload.get("error")
    spec = payload.get("spec")
    assert isinstance(spec, dict)
    assert _spec_has_branches(spec), spec
