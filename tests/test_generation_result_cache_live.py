"""Live Redis + HTTP checks for the organization generation result cache.

Requires a running Redis (same as dashboard e2e). Optional ``LIVE_LLM=1``
adds one real ``/api/generate_graph`` miss and a same-org hit.
"""

from __future__ import annotations

import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from clients.llm.http_client_manager import reset_httpx_clients_for_tests
from models import GenerateRequest
from routers.api import diagram_generation
from services.diagram.generation_result_cache import (
    generation_result_key,
    get_cached_generation_result,
    load_or_generate_cached_result,
    resolve_generation_cache_lookup,
    store_generation_result,
)
from services.llm import llm_service
from services.redis.redis_async_client import close_async_redis, get_async_redis
from services.redis.redis_client import RedisStartupError, init_redis_sync, is_redis_available
from tests.smoke.mindmap_smoke_helpers import live_llm_enabled, mindmap_smoke_helpers_load_dotenv
from utils.auth import get_current_user_or_api_key


def _require_redis() -> None:
    try:
        connected = init_redis_sync()
    except RedisStartupError as exc:
        pytest.skip(f"Redis unavailable — generation cache live tests need Redis: {exc}")
    if not connected or not is_redis_available():
        pytest.skip("Redis unavailable — generation cache live tests need Redis")


def test_require_redis_skips_when_startup_fails() -> None:
    """CI has no Redis; RedisStartupError must skip, not fail the suite."""
    with patch(
        "tests.test_generation_result_cache_live.init_redis_sync",
        side_effect=RedisStartupError("Failed to connect to Redis"),
    ):
        with pytest.raises(pytest.skip.Exception, match="Redis unavailable"):
            _require_redis()


def _org_user(user_id: int, organization_id: int) -> SimpleNamespace:
    return SimpleNamespace(
        id=user_id,
        organization_id=organization_id,
        name=f"teacher-{user_id}",
        role="teacher",
    )


def _success_spec(topic: str) -> dict[str, Any]:
    return {
        "success": True,
        "spec": {"topic": topic, "children": [{"text": "cached-child", "children": []}]},
        "diagram_type": "mind_map",
        "language": "zh",
    }


@pytest.mark.asyncio
async def test_live_redis_store_get_and_org_isolation() -> None:
    """Real Redis stores a spec for org A and does not serve it to org B."""
    _require_redis()
    await close_async_redis()
    fingerprint = f"audit{uuid4().hex}"
    topic = f"cache-audit-{fingerprint[:8]}"
    result = _success_spec(topic)
    try:
        assert await store_generation_result(91001, fingerprint, result) is True
        hit = await get_cached_generation_result(91001, fingerprint)
        assert hit is not None
        assert hit["spec"]["topic"] == topic
        assert "request_id" not in hit
        other = await get_cached_generation_result(91002, fingerprint)
        assert other is None
        redis = get_async_redis()
        assert redis is not None
        ttl = await redis.ttl(generation_result_key(91001, fingerprint))
        assert 1 <= ttl <= 7200
    finally:
        redis = get_async_redis()
        if redis is not None:
            await redis.delete(generation_result_key(91001, fingerprint))
        await close_async_redis()


@pytest.mark.asyncio
async def test_live_second_teacher_reuses_first_without_llm() -> None:
    """Same org + same search: first call generates, second reads Redis."""
    _require_redis()
    await close_async_redis()
    topic = f"aaa-live-{uuid4().hex[:8]}"
    req = GenerateRequest.model_validate(
        {
            "prompt": topic,
            "language": "zh",
            "request_type": "diagram_generation",
        }
    )
    prepared = {
        "req": req,
        "organization_id": 91001,
        "request_type": "diagram_generation",
        "prompt": topic,
        "language": "zh",
        "llm_model": "qwen",
        "generation_instructions": None,
        "is_learning_sheet": False,
    }
    lookup = resolve_generation_cache_lookup(prepared)
    assert lookup is not None
    org_id, fingerprint = lookup
    calls = {"n": 0}

    async def generate() -> dict[str, Any]:
        calls["n"] += 1
        return _success_spec(topic)

    try:
        first = await load_or_generate_cached_result(prepared, generate)
        second = await load_or_generate_cached_result(prepared, generate)
        assert calls["n"] == 1
        assert first["spec"]["topic"] == topic
        assert second["spec"]["topic"] == topic
        assert first["spec"] == second["spec"]
    finally:
        redis = get_async_redis()
        if redis is not None:
            await redis.delete(generation_result_key(org_id, fingerprint))
        await close_async_redis()


def _asgi_app(current: dict[str, SimpleNamespace]) -> FastAPI:
    app = FastAPI()
    app.include_router(diagram_generation.router, prefix="/api")

    async def _user() -> SimpleNamespace:
        return current["user"]

    app.dependency_overrides[get_current_user_or_api_key] = _user
    return app


@pytest.mark.asyncio
async def test_live_http_generate_graph_org_cache_hit() -> None:
    """Two teachers in one org POST the same landing body; the second skips the LLM."""
    _require_redis()
    await close_async_redis()
    topic = f"http-aaa-{uuid4().hex[:8]}"
    current = {"user": _org_user(91011, 91001)}
    calls = {"n": 0}

    async def fake_workflow(**_kwargs: Any) -> dict[str, Any]:
        calls["n"] += 1
        return _success_spec(topic)

    body = {"prompt": topic, "language": "zh", "request_type": "diagram_generation"}
    lookup_req = GenerateRequest.model_validate(body)
    lookup = resolve_generation_cache_lookup(
        {
            "req": lookup_req,
            "organization_id": 91001,
            "request_type": "diagram_generation",
            "prompt": topic,
            "language": "zh",
            "llm_model": "qwen",
            "generation_instructions": None,
            "is_learning_sheet": False,
        }
    )
    assert lookup is not None

    with (
        patch(
            "routers.api.diagram_generation.agent_graph_workflow_with_styles",
            new=AsyncMock(side_effect=fake_workflow),
        ),
        patch("routers.api.diagram_generation.track_module_activity", new=AsyncMock()),
        patch("routers.api.diagram_generation.schedule_user_usage_activity"),
        patch(
            "routers.api.diagram_generation.thinking_coin_post_diagram_generation_mutation",
            new=AsyncMock(return_value=SimpleNamespace(eligible=False)),
        ),
        patch(
            "routers.api.diagram_generation.get_activity_stream_service",
            return_value=SimpleNamespace(broadcast_activity=AsyncMock()),
        ),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=_asgi_app(current)),
            base_url="http://test",
            timeout=30.0,
        ) as client:
            first = await client.post("/api/generate_graph", json=body)
            current["user"] = _org_user(91012, 91001)
            started = time.perf_counter()
            second = await client.post("/api/generate_graph", json=body)
            hit_ms = (time.perf_counter() - started) * 1000
            current["user"] = _org_user(91013, 91099)
            third = await client.post("/api/generate_graph", json=body)

    try:
        assert first.status_code == 200, first.text
        assert second.status_code == 200, second.text
        assert third.status_code == 200, third.text
        assert first.json()["spec"] == second.json()["spec"]
        assert first.json()["diagram_type"] == second.json()["diagram_type"]
        assert calls["n"] == 2
        assert hit_ms < 2000
        assert third.json()["spec"]["topic"] == topic
    finally:
        redis = get_async_redis()
        if redis is not None:
            await redis.delete(generation_result_key(lookup[0], lookup[1]))
            other = resolve_generation_cache_lookup(
                {
                    "req": lookup_req,
                    "organization_id": 91099,
                    "request_type": "diagram_generation",
                    "prompt": topic,
                    "language": "zh",
                    "llm_model": "qwen",
                    "generation_instructions": None,
                    "is_learning_sheet": False,
                }
            )
            if other is not None:
                await redis.delete(generation_result_key(other[0], other[1]))
        await close_async_redis()


@pytest.mark.asyncio
async def test_live_llm_same_org_second_search_hits_cache() -> None:
    """Real Qwen generate once; the second same-org teacher reads Redis."""
    mindmap_smoke_helpers_load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    if not live_llm_enabled():
        pytest.skip("Set LIVE_LLM=1 and QWEN_API_KEY to run the live LLM cache check")
    _require_redis()
    await close_async_redis()
    reset_httpx_clients_for_tests()
    llm_service.initialize()

    topic = f"光合作用缓存审计{uuid4().hex[:6]}"
    current = {"user": _org_user(91021, 91001)}
    body = {
        "prompt": topic,
        "language": "zh",
        "diagram_type": "mind_map",
        "request_type": "diagram_generation",
    }
    lookup = resolve_generation_cache_lookup(
        {
            "req": GenerateRequest.model_validate(body),
            "organization_id": 91001,
            "request_type": "diagram_generation",
            "prompt": topic,
            "language": "zh",
            "llm_model": "qwen",
            "generation_instructions": None,
            "is_learning_sheet": False,
        }
    )
    assert lookup is not None

    try:
        with (
            patch("routers.api.diagram_generation.track_module_activity", new=AsyncMock()),
            patch("routers.api.diagram_generation.schedule_user_usage_activity"),
            patch(
                "routers.api.diagram_generation.thinking_coin_post_diagram_generation_mutation",
                new=AsyncMock(return_value=SimpleNamespace(eligible=False)),
            ),
            patch(
                "routers.api.diagram_generation.get_activity_stream_service",
                return_value=SimpleNamespace(broadcast_activity=AsyncMock()),
            ),
            patch(
                "services.redis.redis_token_buffer.RedisTokenBuffer.track_usage",
                new=AsyncMock(),
            ),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=_asgi_app(current)),
                base_url="http://test",
                timeout=180.0,
            ) as client:
                miss_started = time.perf_counter()
                first = await client.post("/api/generate_graph", json=body)
                miss_ms = (time.perf_counter() - miss_started) * 1000
                current["user"] = _org_user(91022, 91001)
                hit_started = time.perf_counter()
                second = await client.post("/api/generate_graph", json=body)
                hit_ms = (time.perf_counter() - hit_started) * 1000

        assert first.status_code == 200, first.text
        assert second.status_code == 200, second.text
        first_payload = first.json()
        second_payload = second.json()
        assert first_payload.get("success") is True, first_payload.get("error")
        assert second_payload.get("success") is True, second_payload.get("error")
        assert first_payload["spec"] == second_payload["spec"]
        assert first_payload["diagram_type"] == "mind_map"
        assert hit_ms < 2000
        assert hit_ms < miss_ms
        print(f"LIVE_LLM cache miss={miss_ms:.0f}ms hit={hit_ms:.0f}ms topic={topic}")
    finally:
        redis = get_async_redis()
        if redis is not None:
            await redis.delete(generation_result_key(lookup[0], lookup[1]))
        await close_async_redis()
        reset_httpx_clients_for_tests()
