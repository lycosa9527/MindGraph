"""Public static path detection and auth middleware skip tests."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from starlette.requests import ClientDisconnect
from starlette.responses import PlainTextResponse, Response
from starlette.testclient import TestClient

from services.infrastructure.http.exception_handlers import general_exception_handler
from services.infrastructure.http.middleware import (
    auth_context_middleware,
    enforce_streaming_body_limit,
    log_requests,
)
from services.infrastructure.utils.spa_handler import is_public_static_path


@pytest.mark.parametrize(
    "path",
    [
        "/assets/vendor-keyboard-BHem4BCl.js",
        "/assets/noto-sans-sc-chinese-simplified-400-normal-Ba7eOkfT.woff2",
        "/static/community/thumb.png",
        "/gallery/featured/foo.png",
        "/favicon.svg",
        "/robots.txt",
        "/pwa-512x512.png",
        "/manifest.webmanifest",
        "/sw.js",
        "/workbox-abc123.js",
        "/health",
        "/healthz",
    ],
)
def test_is_public_static_path_true(path: str) -> None:
    """Test is public static path true."""
    assert is_public_static_path(path) is True


@pytest.mark.parametrize(
    "path",
    [
        "/api/auth/me",
        "/mindgraph",
        "/canvas",
        "/login",
        "/",
    ],
)
def test_is_public_static_path_false_for_app_routes(path: str) -> None:
    """Test is public static path false for app routes."""
    assert is_public_static_path(path) is False


def _app_with_auth_middleware() -> FastAPI:
    """App with auth middleware."""
    app = FastAPI()
    app.middleware("http")(auth_context_middleware)

    @app.get("/assets/{name}")
    async def fake_asset(name: str) -> PlainTextResponse:
        return PlainTextResponse(f"asset:{name}")

    @app.get("/api/ping")
    async def api_ping() -> PlainTextResponse:
        return PlainTextResponse("pong")

    return app


def test_auth_middleware_skips_session_for_assets() -> None:
    """Test auth middleware skips session for assets."""
    app = _app_with_auth_middleware()
    resolve_mock = AsyncMock(return_value=None)
    with patch(
        "services.infrastructure.http.middleware.resolve_authenticated_user_optional",
        resolve_mock,
    ):
        client = TestClient(app)
        response = client.get("/assets/chunk-abc.js")
    assert response.status_code == 200
    resolve_mock.assert_not_called()


def test_auth_middleware_resolves_user_for_api() -> None:
    """Test auth middleware resolves user for api."""
    app = _app_with_auth_middleware()
    resolve_mock = AsyncMock(return_value=None)
    with patch(
        "services.infrastructure.http.middleware.resolve_authenticated_user_optional",
        resolve_mock,
    ):
        client = TestClient(app)
        response = client.get("/api/ping")
    assert response.status_code == 200
    resolve_mock.assert_called_once()


def _app_with_log_middleware() -> FastAPI:
    """App with log middleware."""
    app = FastAPI()
    app.middleware("http")(log_requests)

    @app.get("/assets/{name}")
    async def fake_asset(_name: str) -> PlainTextResponse:
        return PlainTextResponse("ok")

    @app.get("/api/ping")
    async def api_ping() -> PlainTextResponse:
        return PlainTextResponse("pong")

    @app.post("/api/generate_graph/stream")
    async def generate_graph_stream() -> PlainTextResponse:
        return PlainTextResponse("ok")

    return app


def test_log_requests_skips_debug_line_for_assets(caplog: pytest.LogCaptureFixture) -> None:
    """Test log requests skips debug line for assets."""
    caplog.set_level("DEBUG")
    client = TestClient(_app_with_log_middleware())
    client.get("/assets/chunk.js")
    assert not any("Request: GET /assets/" in record.message for record in caplog.records)


def test_log_requests_keeps_debug_line_for_api(caplog: pytest.LogCaptureFixture) -> None:
    """Test log requests keeps debug line for api."""
    caplog.set_level("DEBUG")
    client = TestClient(_app_with_log_middleware())
    client.get("/api/ping")
    assert any("Request: GET /api/ping" in record.message for record in caplog.records)


def test_log_requests_does_not_buffer_generate_graph_body() -> None:
    """Logging must not consume the body (avoids ClientDisconnect → 500)."""
    client = TestClient(_app_with_log_middleware())
    response = client.post(
        "/api/generate_graph/stream",
        json={"request_type": "autocomplete", "topic": "x"},
    )
    assert response.status_code == 200
    assert response.text == "ok"


@pytest.mark.asyncio
async def test_log_requests_never_reads_body() -> None:
    """Unit: log_requests must not call request.body()."""
    request = MagicMock()
    request.method = "POST"
    request.url = SimpleNamespace(path="/api/generate_graph/stream", query="")
    request.body = AsyncMock(return_value=b'{"request_type":"autocomplete"}')
    request.state = SimpleNamespace()
    call_next = AsyncMock(return_value=Response(status_code=200))

    response = await log_requests(request, call_next)

    assert response.status_code == 200
    request.body.assert_not_called()
    call_next.assert_awaited_once()


@pytest.mark.asyncio
async def test_enforce_streaming_body_limit_returns_204_on_client_disconnect() -> None:
    """Client abort while buffering a chunked body must not become a 500."""
    request = MagicMock()
    request.method = "POST"
    request.url = SimpleNamespace(path="/api/upload")
    request.headers = {}
    request.body = AsyncMock(side_effect=ClientDisconnect())
    call_next = AsyncMock()

    with patch(
        "services.infrastructure.http.middleware.max_request_body_size_for_path",
        return_value=1024,
    ):
        response = await enforce_streaming_body_limit(request, call_next)

    assert response.status_code == 204
    call_next.assert_not_called()


@pytest.mark.asyncio
async def test_general_exception_handler_treats_client_disconnect_as_204() -> None:
    """Safety net when ClientDisconnect escapes outer middleware into ServerErrorMiddleware."""
    request = MagicMock()
    request.url = SimpleNamespace(path="/api/generate_graph/stream")
    request.state = SimpleNamespace(request_id=None)

    response = await general_exception_handler(request, ClientDisconnect())

    assert response.status_code == 204


@pytest.mark.asyncio
async def test_general_exception_handler_reroutes_http_exception() -> None:
    """Middleware-raised HTTPException must not become an unhandled 500."""
    request = MagicMock()
    request.url = SimpleNamespace(path="/api/auth/me")
    request.state = SimpleNamespace(request_id=None)
    request.headers = {}

    response = await general_exception_handler(
        request,
        HTTPException(status_code=401, detail="Invalid or expired token"),
    )

    assert response.status_code == 401
    assert response.body == b'{"detail":"Invalid or expired token"}'
