"""Cross-check SPA cache helpers against Vue router and vue_spa routes."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from services.infrastructure.utils.spa_handler import is_spa_route, should_apply_no_cache

_ROUTER_PATH = Path(__file__).resolve().parents[2] / 'frontend' / 'src' / 'router' / 'index.ts'

_NON_SPA_PREFIXES = ('/api', '/static', '/assets', '/gallery', '/ws', '/thinking_mode')
_NON_SPA_EXACT = frozenset({'/health', '/healthz', '/ready', '/docs', '/redoc', '/openapi.json'})


def _router_paths() -> list[str]:
    text = _ROUTER_PATH.read_text(encoding='utf-8')
    paths = re.findall(r"path:\s*['\"]([^'\"]+)['\"]", text)
    return [
        path
        for path in paths
        if ':' not in path and not path.startswith('*')
    ]


def _has_file_extension(path: str) -> bool:
    segment = path.rstrip('/').split('/')[-1]
    return bool(segment) and '.' in segment


@pytest.mark.parametrize(
    'path',
    _router_paths(),
    ids=_router_paths(),
)
def test_vue_router_extensionless_paths_are_spa_routes(path: str) -> None:
    if any(path.startswith(prefix) for prefix in _NON_SPA_PREFIXES):
        pytest.skip('backend-only prefix')
    if path in _NON_SPA_EXACT:
        pytest.skip('backend-only exact path')
    if _has_file_extension(path):
        pytest.skip('static file extension')
    assert is_spa_route(path) is True
    assert should_apply_no_cache(path) is True


@pytest.mark.parametrize(
    'path',
    [
        '/',
        '/editor',
        '/admin',
        '/login',
        '/auth',
        '/bayi/passkey',
        '/dashboard',
        '/dashboard/login',
        '/pub-dash',
        '/debug',
        '/mindmate',
        '/mindgraph',
        '/canvas',
        '/export-render',
        '/template',
        '/course',
        '/community',
        '/school-zone',
        '/knowledge-space',
        '/askonce',
        '/debateverse',
        '/index.html',
    ],
)
def test_vue_spa_served_paths_get_no_cache(path: str) -> None:
    assert should_apply_no_cache(path) is True


@pytest.mark.parametrize(
    'path',
    [
        '/sw.js',
        '/manifest.webmanifest',
        '/workbox-deadbeef.js',
        '/workbox-deadbeef.mjs',
    ],
)
def test_pwa_bootstrap_paths_get_no_cache(path: str) -> None:
    assert should_apply_no_cache(path) is True
