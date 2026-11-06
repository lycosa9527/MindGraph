"""Upgrade public media URLs from http to https.

Loopback hosts stay on the scheme they were given so local Vite and Uvicorn
keep working. Every other host is rewritten to https, including an
``EXTERNAL_BASE_URL`` that was set with ``http://``.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import re
from urllib.parse import urlsplit, urlunsplit

from utils.public_hosts import rewrite_legacy_public_origin

_HTTP_URL_RE = re.compile(r"https?://[^\s\"'<>)]+", re.IGNORECASE)
_PUBLIC_MEDIA_MARKERS = ("/temp_images/", "/zhihui/assets/")


def is_loopback_host(host: str) -> bool:
    """True for localhost and 127.0.0.0/8."""
    name = (host or "").lower().strip()
    if name in ("localhost", "127.0.0.1", "::1"):
        return True
    if name.count(".") == 3 and name.startswith("127."):
        return all(part.isdigit() and 0 <= int(part) <= 255 for part in name.split("."))
    return False


def strip_leading_http_schemes(value: str) -> str:
    """Remove leading http:// and https:// prefixes, repeatedly.

    Some reverse proxies send a full URL in X-Forwarded-Host. The host part
    must not include a scheme, since the caller supplies the scheme separately.
    """
    result = (value or "").strip()
    while True:
        lower = result.lower()
        if lower.startswith("https://"):
            result = result[8:]
        elif lower.startswith("http://"):
            result = result[7:]
        else:
            break
    return result


def collapse_double_scheme_base_url(value: str) -> str:
    """Fix EXTERNAL_BASE_URL values like http://https://host when mis-set."""
    result = (value or "").strip()
    for _ in range(3):
        lower = result.lower()
        if lower.startswith("http://https://"):
            result = result[7:]
        elif lower.startswith("https://http://"):
            result = result[8:]
        else:
            break
    return result.rstrip("/")


def _strip_redundant_trailing_api_path(base: str) -> str:
    """Drop a mistaken trailing /api so links are not .../api/api/..."""
    trimmed = (base or "").strip().rstrip("/")
    if len(trimmed) >= 4 and trimmed[-4:].lower() == "/api":
        return trimmed[:-4].rstrip("/")
    return trimmed


def normalize_external_base_url(value: str) -> str:
    """Canonical public site base.

    Fixes a doubled scheme, trims slashes, drops a mistaken trailing ``/api``,
    and requires an http(s) scheme (otherwise empty). A public http base is
    returned as https. Loopback stays http.
    """
    collapsed = collapse_double_scheme_base_url(value)
    if not collapsed:
        return ""
    no_dup_api = _strip_redundant_trailing_api_path(collapsed)
    low = no_dup_api.lower()
    if not (low.startswith("http://") or low.startswith("https://")):
        return ""
    return rewrite_legacy_public_origin(upgrade_public_http_url(no_dup_api))


def upgrade_public_http_url(url: str) -> str:
    """Return ``url`` with https when the host is not loopback."""
    raw = (url or "").strip()
    parts = urlsplit(raw)
    if parts.scheme.lower() != "http":
        return raw
    host = (parts.hostname or "").lower()
    if not host or is_loopback_host(host):
        return raw
    port = parts.port
    if port in (None, 80):
        netloc = f"[{host}]" if ":" in host else host
    else:
        netloc = parts.netloc
    return urlunsplit(("https", netloc, parts.path, parts.query, parts.fragment))


def upgrade_public_media_url(url: str) -> str:
    """Upgrade http to https for temp-image and Zhihui asset URLs."""
    raw = (url or "").strip()
    path = urlsplit(raw).path.lower()
    if not any(marker in path for marker in _PUBLIC_MEDIA_MARKERS):
        return raw
    return rewrite_legacy_public_origin(upgrade_public_http_url(raw))


def upgrade_public_media_urls_in_text(text: str) -> str:
    """Rewrite public temp-image and asset links to https on www."""

    def _replace(match: re.Match[str]) -> str:
        return upgrade_public_media_url(match.group(0))

    return _HTTP_URL_RE.sub(_replace, text or "")
