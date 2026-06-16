"""Public static path detection and auth middleware skip tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from starlette.responses import PlainTextResponse
from starlette.testclient import TestClient

from services.infrastructure.http.middleware import auth_context_middleware, log_requests
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
    assert is_public_static_path(path) is False


def _app_with_auth_middleware() -> FastAPI:
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
    app = FastAPI()
    app.middleware("http")(log_requests)

    @app.get("/assets/{name}")
    async def fake_asset(_name: str) -> PlainTextResponse:
        return PlainTextResponse("ok")

    @app.get("/api/ping")
    async def api_ping() -> PlainTextResponse:
        return PlainTextResponse("pong")

    return app


def test_log_requests_skips_debug_line_for_assets(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("DEBUG")
    client = TestClient(_app_with_log_middleware())
    client.get("/assets/chunk.js")
    assert not any("Request: GET /assets/" in record.message for record in caplog.records)


def test_log_requests_keeps_debug_line_for_api(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("DEBUG")
    client = TestClient(_app_with_log_middleware())
    client.get("/api/ping")
    assert any("Request: GET /api/ping" in record.message for record in caplog.records)
