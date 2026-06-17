"""PWA web app manifest helpers (origin resolution + manifest payload).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import os

from fastapi import Request

from routers.api.helpers import normalize_external_base_url, strip_leading_http_schemes
from utils.auth.request_helpers import is_https


def public_site_origin_from_request(request: Request) -> str:
    """Resolve public https?://host[:port] for manifest start_url (proxy-aware)."""
    external_base = normalize_external_base_url(os.getenv("EXTERNAL_BASE_URL", ""))
    if external_base:
        return external_base

    forwarded_proto = (request.headers.get("X-Forwarded-Proto") or "").strip()
    forwarded_host_raw = (request.headers.get("X-Forwarded-Host") or "").strip()
    if forwarded_proto and forwarded_host_raw:
        host_only = strip_leading_http_schemes(forwarded_host_raw).strip().rstrip("/")
        if host_only:
            return f"{forwarded_proto}://{host_only}"

    scheme = "https" if is_https(request) else request.url.scheme
    raw_host = strip_leading_http_schemes(request.headers.get("Host") or request.url.netloc or "localhost")
    host = raw_host.split(",")[0].strip().rstrip("/")
    return f"{scheme}://{host}".rstrip("/")


def build_pwa_manifest(origin: str) -> dict:
    """Build manifest JSON with absolute start_url/id so installed apps open the live origin."""
    base = origin.rstrip("/")
    return {
        "name": "MindGraph",
        "short_name": "MindGraph",
        "description": "AI-powered mind mapping and teaching platform",
        "lang": "en",
        "dir": "ltr",
        "theme_color": "#1c1917",
        "background_color": "#1c1917",
        "display": "standalone",
        "display_override": ["standalone", "minimal-ui"],
        "orientation": "any",
        "prefer_related_applications": False,
        "categories": ["education", "productivity"],
        "start_url": f"{base}/",
        "scope": "/",
        "id": f"{base}/",
        "icons": [
            {
                "src": "/pwa-192x192.png",
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "any",
            },
            {
                "src": "/pwa-512x512.png",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "any",
            },
            {
                "src": "/pwa-512x512.png",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "maskable",
            },
        ],
    }
