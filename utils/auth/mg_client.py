"""
Resolve and sanitize X-MG-Client labels for mgat_ / session traffic.

External clients (Chrome/Edge extension, OpenClaw, file-reader) send
``X-MG-Client`` with every API-token request. Browser JWT sessions are
labeled ``web``. Values are bound on ``request.state`` once per request so
activity tracking and logs can attribute traffic without re-parsing headers.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Optional

from fastapi import Request

from utils.auth.connection_types import HttpOrWebSocket

MG_CLIENT_HEADER = "X-MG-Client"
REQUEST_STATE_MG_CLIENT = "mg_client"

MG_CLIENT_WEB = "web"
MG_CLIENT_UNSPECIFIED = "unspecified"

# Canonical labels shipped by first-party clients (keep in sync with docs / clients).
KNOWN_MG_CLIENTS = frozenset(
    {
        MG_CLIENT_WEB,
        "chrome-extension",
        "edge-extension",
        "openclaw",
        "file-reader",
        MG_CLIENT_UNSPECIFIED,
    }
)

MG_CLIENT_DISPLAY_LABELS = {
    MG_CLIENT_WEB: "Web",
    "chrome-extension": "Chrome extension",
    "edge-extension": "Edge extension",
    "openclaw": "OpenClaw",
    "file-reader": "File reader",
    MG_CLIENT_UNSPECIFIED: "Unspecified",
}

# Lowercase slug: letter, then letters/digits/hyphens (max 64 incl. first char).
_MG_CLIENT_SLUG_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")


def sanitize_mg_client_label(raw: Optional[str]) -> str:
    """
    Normalize a client label for logs and activity details.

    Missing/invalid values become ``unspecified``. Well-formed unknown slugs
    are kept (forward-compatible with new clients).
    """
    if not raw or not isinstance(raw, str):
        return MG_CLIENT_UNSPECIFIED
    cleaned = raw.strip().lower()
    if not cleaned:
        return MG_CLIENT_UNSPECIFIED
    if len(cleaned) > 64:
        cleaned = cleaned[:64]
    if not _MG_CLIENT_SLUG_RE.match(cleaned):
        return MG_CLIENT_UNSPECIFIED
    return cleaned


def mg_client_display_label(client: Optional[str]) -> str:
    """Human-readable label for admin / activity UIs."""
    if not client:
        return MG_CLIENT_DISPLAY_LABELS[MG_CLIENT_UNSPECIFIED]
    return MG_CLIENT_DISPLAY_LABELS.get(client, client)


def get_bound_mg_client(request: Optional[HttpOrWebSocket]) -> Optional[str]:
    """Return previously bound ``request.state.mg_client``, if any."""
    if request is None:
        return None
    value = getattr(request.state, REQUEST_STATE_MG_CLIENT, None)
    if isinstance(value, str) and value:
        return value
    return None


def bind_mg_client(request: Optional[HttpOrWebSocket], client: str) -> str:
    """Store a sanitized client label on the request and return it."""
    label = sanitize_mg_client_label(client)
    if request is not None:
        setattr(request.state, REQUEST_STATE_MG_CLIENT, label)
    return label


def bind_mg_client_from_header(request: Optional[Request]) -> str:
    """Bind from ``X-MG-Client`` (mgat_ path). Missing header → unspecified."""
    if request is None:
        return MG_CLIENT_UNSPECIFIED
    raw = request.headers.get(MG_CLIENT_HEADER) or ""
    return bind_mg_client(request, raw)


def bind_mg_client_for_web(request: Optional[Request]) -> str:
    """Bind browser JWT / cookie session traffic as ``web``."""
    return bind_mg_client(request, MG_CLIENT_WEB)


def client_source_from_request(request: Optional[HttpOrWebSocket]) -> Optional[str]:
    """
    Best-effort client source for activity / logging.

    Prefers a value already bound during auth; otherwise resolves from
    ``X-MG-Client`` without forcing ``web`` (unauthenticated paths stay None).
    """
    bound = get_bound_mg_client(request)
    if bound:
        return bound
    if request is None:
        return None
    raw = request.headers.get(MG_CLIENT_HEADER)
    if not raw or not str(raw).strip():
        return None
    return sanitize_mg_client_label(raw)


def merge_client_source_into_details(
    details: Optional[Mapping[str, Any]],
    client_source: Optional[str],
) -> dict[str, Any]:
    """Copy details and set ``client_source`` when provided."""
    merged: dict[str, Any] = dict(details) if details else {}
    if client_source:
        merged.setdefault("client_source", client_source)
    return merged


def activity_details_with_request_client(
    details: Optional[Mapping[str, Any]],
    request: Optional[HttpOrWebSocket],
) -> dict[str, Any]:
    """Merge request client source into activity details."""
    return merge_client_source_into_details(details, client_source_from_request(request))
