"""SPA route detection and HTTP cache-control middleware tests."""

from __future__ import annotations

import importlib

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse, PlainTextResponse
from starlette.responses import Response
from starlette.testclient import TestClient

from services.infrastructure.http.middleware import add_cache_control_headers
from services.infrastructure.utils.spa_handler import (
    apply_no_cache_headers,
    is_pwa_no_cache_path,
    is_spa_route,
    should_apply_api_no_cache,
    should_apply_no_cache,
)

vue_spa_module = importlib.import_module('routers.core.vue_spa')


@pytest.mark.parametrize(
    'path',
    [
        '/',
        '/mindmate',
        '/mindgraph',
        '/canvas',
        '/auth',
        '/login',
        '/admin',
        '/admin/settings',
        '/bayi/passkey',
        '/dashboard',
        '/dashboard/login',
        '/library',
        '/library/abc-123',
        '/library/bookmark/uuid-here',
        '/workshop-chat',
        '/export-render',
        '/m',
        '/m/canvas',
        '/chunk-test/results/42',
    ],
)
def test_is_spa_route_true_for_client_routes(path: str) -> None:
    assert is_spa_route(path) is True


@pytest.mark.parametrize(
    'path',
    [
        '/api/auth/me',
        '/static/community/thumb.png',
        '/assets/index-abc123.js',
        '/gallery/featured/foo.png',
        '/ws/workshop',
        '/thinking_mode/stream',
        '/health',
        '/docs',
        '/openapi.json',
        '/favicon.svg',
        '/robots.txt',
        '/pwa-512x512.png',
        '/nested/offline.html',
    ],
)
def test_is_spa_route_false_for_non_client_routes(path: str) -> None:
    assert is_spa_route(path) is False


@pytest.mark.parametrize(
    'path',
    [
        '/manifest.webmanifest',
        '/sw.js',
        '/workbox-abc123.js',
        '/workbox-abc123.mjs',
    ],
)
def test_is_pwa_no_cache_path(path: str) -> None:
    assert is_pwa_no_cache_path(path) is True
    assert should_apply_no_cache(path) is True


def test_should_apply_no_cache_html_by_suffix_and_content_type() -> None:
    assert should_apply_no_cache('/nested/offline.html') is True
    assert should_apply_no_cache('/unexpected', 'text/html; charset=utf-8') is True


def test_should_apply_api_no_cache_only_when_unset() -> None:
    response = Response()
    assert should_apply_api_no_cache('/api/auth/me', response) is True

    response.headers['Cache-Control'] = 'public, max-age=3600'
    assert should_apply_api_no_cache('/api/library/image', response) is False

    assert should_apply_api_no_cache('/mindmate', response) is False


def test_apply_no_cache_headers() -> None:
    response = Response()
    apply_no_cache_headers(response)
    assert response.headers['Cache-Control'] == 'no-cache, no-store, must-revalidate'
    assert response.headers['Pragma'] == 'no-cache'
    assert response.headers['Expires'] == '0'


def _app_with_cache_middleware() -> FastAPI:
    app = FastAPI()
    app.middleware('http')(add_cache_control_headers)

    @app.get('/assets/{name}')
    async def fake_asset(name: str) -> PlainTextResponse:
        return PlainTextResponse(f'asset:{name}')

    @app.get('/api/ping')
    async def api_ping() -> JSONResponse:
        return JSONResponse({'ok': True})

    @app.get('/api/cached-image')
    async def api_cached_image() -> Response:
        return Response(
            content=b'png',
            media_type='image/png',
            headers={'Cache-Control': 'public, max-age=3600'},
        )

    app.include_router(vue_spa_module.router)
    return app


def test_middleware_no_cache_on_spa_route(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    dist_dir = tmp_path / 'dist'
    dist_dir.mkdir()
    (dist_dir / 'index.html').write_text(
        '<!doctype html><html><body>spa</body></html>',
        encoding='utf-8',
    )
    monkeypatch.setattr(vue_spa_module, 'VUE_DIST_DIR', dist_dir)

    client = TestClient(_app_with_cache_middleware())
    for path in ('/', '/index.html', '/mindmate', '/library/bookmark/uuid', '/m/canvas'):
        response = client.get(path)
        assert response.status_code == 200
        assert response.headers['Cache-Control'] == 'no-cache, no-store, must-revalidate'


def test_middleware_immutable_assets() -> None:
    client = TestClient(_app_with_cache_middleware())
    response = client.get('/assets/chunk-abc.js')
    assert response.status_code == 200
    assert 'immutable' in response.headers['Cache-Control']


def test_middleware_api_default_no_cache() -> None:
    client = TestClient(_app_with_cache_middleware())
    response = client.get('/api/ping')
    assert response.status_code == 200
    assert response.headers['Cache-Control'] == 'no-cache, no-store, must-revalidate'


def test_middleware_preserves_api_handler_cache_control() -> None:
    client = TestClient(_app_with_cache_middleware())
    response = client.get('/api/cached-image')
    assert response.status_code == 200
    assert response.headers['Cache-Control'] == 'public, max-age=3600'
