"""PWA manifest origin resolution and payload tests."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from starlette.requests import Request

from services.infrastructure.utils.pwa_manifest import (
    build_pwa_manifest,
    public_site_origin_from_request,
)


def _request(
    path: str = '/manifest.webmanifest',
    headers: list[tuple[bytes, bytes]] | None = None,
) -> Request:
    header_list = headers or [(b'host', b'app.example.com')]
    scope = {
        'type': 'http',
        'method': 'GET',
        'path': path,
        'headers': header_list,
        'scheme': 'http',
        'server': ('app.example.com', 443),
        'client': ('127.0.0.1', 12345),
    }
    return Request(scope)


def test_build_pwa_manifest_uses_absolute_start_url_and_id() -> None:
    manifest = build_pwa_manifest('https://mindgraph.example.com')
    assert manifest['start_url'] == 'https://mindgraph.example.com/'
    assert manifest['id'] == 'https://mindgraph.example.com/'
    assert manifest['scope'] == '/'
    assert manifest['display'] == 'standalone'
    assert manifest['prefer_related_applications'] is False
    assert manifest['icons'][0]['src'] == '/pwa-192x192.png'


def test_public_site_origin_prefers_external_base_url() -> None:
    request = _request()
    with patch.dict(os.environ, {'EXTERNAL_BASE_URL': 'https://public.example.com'}, clear=False):
        assert public_site_origin_from_request(request) == 'https://public.example.com'


def test_public_site_origin_uses_forwarded_headers() -> None:
    request = _request(
        headers=[
            (b'x-forwarded-proto', b'https'),
            (b'x-forwarded-host', b'edge.example.com'),
        ]
    )
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop('EXTERNAL_BASE_URL', None)
        assert public_site_origin_from_request(request) == 'https://edge.example.com'


def test_public_site_origin_falls_back_to_host_header() -> None:
    request = _request(headers=[(b'host', b'localhost:9527')])
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop('EXTERNAL_BASE_URL', None)
        assert public_site_origin_from_request(request) == 'http://localhost:9527'


@pytest.mark.parametrize(
    ('platform_label', 'origin'),
    [
        ('Windows production HTTPS', 'https://app.mindgraph.com'),
        ('macOS production HTTPS', 'https://mac.mindgraph.com'),
        ('Windows localhost dev', 'http://localhost:9527'),
        ('macOS localhost dev', 'http://127.0.0.1:9527'),
    ],
)
def test_manifest_start_url_never_uses_file_scheme(platform_label: str, origin: str) -> None:
    _ = platform_label
    manifest = build_pwa_manifest(origin)
    assert manifest['start_url'].startswith('http://') or manifest['start_url'].startswith('https://')
    assert not manifest['start_url'].startswith('file://')
