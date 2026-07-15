"""
End-to-end coverage for the national China-map dashboard.

Uses httpx ASGITransport on a single asyncio event loop so the shared
redis.asyncio client stays bound to one loop.

Requires Redis. Authenticated calls use FastAPI dependency overrides for a
platform super-admin (no passkey).
"""

from __future__ import annotations

import asyncio
import importlib
import json
import shutil
from collections.abc import AsyncIterator, Generator
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport

from main import app
from routers.auth.dependencies import get_language_dependency
from services.redis.redis_async_client import close_async_redis
from services.redis.redis_client import init_redis_sync, is_redis_available
from utils.auth import get_current_user


def _make_superadmin(user_id: int = 1) -> SimpleNamespace:
    user = SimpleNamespace()
    user.id = user_id
    user.role = "superadmin"
    user.organization_id = None
    return user


def _as_superadmin() -> None:
    app.dependency_overrides[get_current_user] = _make_superadmin
    app.dependency_overrides[get_language_dependency] = lambda: "en"


@pytest.fixture(scope="module", autouse=True)
def _init_sync_redis() -> None:
    """Initialize sync Redis used by rate limiting / activity helpers."""
    if not init_redis_sync():
        pytest.skip("Redis init failed — dashboard APIs use Redis")
    if not is_redis_available():
        pytest.skip("Redis unavailable — dashboard APIs use Redis")


@pytest_asyncio.fixture(name="client")
async def fixture_client() -> AsyncIterator[httpx.AsyncClient]:
    """Async HTTP client sharing one event loop with redis.asyncio."""
    await close_async_redis()
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"X-Forwarded-For": "203.0.113.50"},
    ) as client:
        yield client
    await close_async_redis()


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> Generator[None, None, None]:
    """Clear FastAPI dependency overrides after each test."""
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_stats_requires_superadmin(client: httpx.AsyncClient) -> None:
    """Unauthenticated stats calls must be rejected."""
    response = await client.get("/api/public/stats")
    assert response.status_code in {401, 403}


@pytest.mark.asyncio
async def test_stats_rejects_non_superadmin(client: httpx.AsyncClient) -> None:
    """School managers must not access national dashboard APIs."""
    user = SimpleNamespace()
    user.id = 42
    user.role = "school_admin"
    user.organization_id = 7
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_language_dependency] = lambda: "en"
    response = await client.get("/api/public/stats")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_full_dashboard_flow_stats_map_activity(client: httpx.AsyncClient) -> None:
    """Super-admin → stats / map-data / activity-history response shapes."""
    _as_superadmin()

    stats = await client.get("/api/public/stats")
    assert stats.status_code == 200, stats.text
    stats_body = stats.json()
    for key in (
        "connected_users",
        "registered_users",
        "tokens_used_today",
        "total_tokens_used",
    ):
        assert key in stats_body
        assert isinstance(stats_body[key], int)

    map_resp = await client.get("/api/public/map-data")
    assert map_resp.status_code == 200, map_resp.text
    map_body = map_resp.json()
    assert "map_data" in map_body
    assert "flag_data" in map_body
    assert isinstance(map_body["map_data"], list)
    assert isinstance(map_body["flag_data"], list)
    for item in map_body["map_data"]:
        assert "name" in item
        assert "value" in item
    for flag in map_body["flag_data"]:
        assert "name" in flag
        assert "value" in flag
        assert isinstance(flag["value"], list)
        assert len(flag["value"]) >= 2

    history = await client.get("/api/public/activity-history?limit=20")
    assert history.status_code == 200, history.text
    history_body = history.json()
    assert "activities" in history_body
    assert isinstance(history_body["activities"], list)
    for activity in history_body["activities"]:
        assert "timestamp" in activity
        assert "user" in activity


@pytest.mark.asyncio
async def test_activity_stream_requires_auth(client: httpx.AsyncClient) -> None:
    """SSE rejects anonymous clients."""
    denied = await client.get("/api/public/activity-stream")
    assert denied.status_code in {401, 403}


@pytest.mark.asyncio
async def test_activity_stream_emits_initial_event(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Authenticated SSE yields an initial framed event, then exits the poll loop."""
    _as_superadmin()

    async def _finite_sleep(_seconds: float) -> None:
        raise asyncio.CancelledError()

    monkeypatch.setattr("routers.public_dashboard.asyncio.sleep", _finite_sleep)

    async with client.stream(
        "GET",
        "/api/public/activity-stream",
        timeout=httpx.Timeout(20.0),
    ) as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")
        collected = ""
        async for chunk in response.aiter_text():
            collected += chunk
            if "\n\n" in collected:
                break
            if len(collected) > 8000:
                break

    assert "data:" in collected
    payload_lines = [
        line[5:].strip()
        for line in collected.splitlines()
        if line.startswith("data:")
    ]
    assert payload_lines
    parsed = json.loads(payload_lines[0])
    assert parsed.get("type") in {"initial", "error", "heartbeat", "stats_update", "activity"}
    if parsed.get("type") == "initial":
        assert "stats" in parsed


@pytest.mark.asyncio
async def test_china_geo_static_asset_served(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    """China GeoJSON used by the Vue map must be reachable under /data (frontend dist)."""
    vue_spa_module = importlib.import_module("routers.core.vue_spa")
    dist_dir = tmp_path / "dist"
    data_dir = dist_dir / "data"
    data_dir.mkdir(parents=True)
    source = Path("frontend/public/data/china-geo.json")
    if not source.is_file():
        pytest.skip("frontend/public/data/china-geo.json not present")
    shutil.copy(source, data_dir / "china-geo.json")
    monkeypatch.setattr(vue_spa_module, "VUE_DIST_DIR", dist_dir)

    response = await client.get("/data/china-geo.json")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body.get("type") == "FeatureCollection"
    assert isinstance(body.get("features"), list)
    assert len(body["features"]) > 10


@pytest.mark.asyncio
async def test_spa_routes_redirect_dashboard_to_admin(client: httpx.AsyncClient) -> None:
    """Legacy dashboard URLs redirect to the admin national data center."""
    expected = "/admin?tab=settings&subtab=public_dashboard"
    for path in ("/dashboard", "/dashboard/login", "/pub-dash"):
        response = await client.get(path, follow_redirects=False)
        assert response.status_code in {301, 302, 307, 308}, f"{path} -> {response.status_code}"
        location = response.headers.get("location", "")
        assert location.endswith(expected) or expected in location, (
            f"{path} location={location!r}"
        )
