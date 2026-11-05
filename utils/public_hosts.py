"""Canonical public hostname for MindGraph.

``www.mindspringedu.com`` is the public origin the app emits. ``mg`` is accepted
on the way in and rewritten to ``www`` on every link the server builds, including
DingTalk callbacks and preview images.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit

CANONICAL_PUBLIC_HOST = "www.mindspringedu.com"
LEGACY_PUBLIC_HOST = "mg.mindspringedu.com"
CANONICAL_PUBLIC_ORIGIN = f"https://{CANONICAL_PUBLIC_HOST}"
LEGACY_PUBLIC_ORIGIN = f"https://{LEGACY_PUBLIC_HOST}"

FIRST_PARTY_PUBLIC_HOSTS = frozenset({CANONICAL_PUBLIC_HOST, LEGACY_PUBLIC_HOST})
FIRST_PARTY_HTTPS_ORIGINS = frozenset({CANONICAL_PUBLIC_ORIGIN, LEGACY_PUBLIC_ORIGIN})


def rewrite_legacy_public_origin(url: str) -> str:
    """Return ``url`` with the legacy ``mg`` host replaced by ``www``."""
    raw = (url or "").strip()
    if not raw:
        return raw
    parts = urlsplit(raw)
    host = (parts.hostname or "").lower()
    if host != LEGACY_PUBLIC_HOST:
        return raw
    port = parts.port
    if port in (None, 80, 443):
        netloc = CANONICAL_PUBLIC_HOST
    else:
        netloc = f"{CANONICAL_PUBLIC_HOST}:{port}"
    scheme = parts.scheme.lower()
    if scheme == "http":
        scheme = "https"
    return urlunsplit((scheme or "https", netloc, parts.path, parts.query, parts.fragment))
