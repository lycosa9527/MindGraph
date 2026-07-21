"""Tests for X-MG-Client sanitization and activity attribution helpers."""

from __future__ import annotations

from unittest.mock import MagicMock

from utils.auth.mg_client import (
    KNOWN_MG_CLIENTS,
    MG_CLIENT_UNSPECIFIED,
    MG_CLIENT_WEB,
    REQUEST_STATE_MG_CLIENT,
    activity_details_with_request_client,
    bind_mg_client_for_web,
    bind_mg_client_from_header,
    client_source_from_request,
    mg_client_display_label,
    sanitize_mg_client_label,
)


def test_sanitize_known_clients() -> None:
    """First-party client labels normalize to canonical slugs."""
    assert sanitize_mg_client_label("Chrome-Extension") == "chrome-extension"
    assert sanitize_mg_client_label(" openclaw ") == "openclaw"
    assert sanitize_mg_client_label("file-reader") == "file-reader"
    assert "chrome-extension" in KNOWN_MG_CLIENTS


def test_sanitize_rejects_garbage() -> None:
    """Invalid or empty labels become unspecified."""
    assert sanitize_mg_client_label("") == MG_CLIENT_UNSPECIFIED
    assert sanitize_mg_client_label(None) == MG_CLIENT_UNSPECIFIED
    assert sanitize_mg_client_label("!!!") == MG_CLIENT_UNSPECIFIED
    assert sanitize_mg_client_label("has spaces") == MG_CLIENT_UNSPECIFIED
    assert sanitize_mg_client_label("Bad_Client") == MG_CLIENT_UNSPECIFIED


def test_sanitize_keeps_forward_compatible_slug() -> None:
    """Unknown but well-formed slugs are preserved for new clients."""
    assert sanitize_mg_client_label("future-client-v2") == "future-client-v2"


def test_bind_mgat_header_on_request() -> None:
    """mgat path binds sanitized X-MG-Client onto request.state."""
    request = MagicMock()
    request.headers = {"X-MG-Client": "chrome-extension"}
    request.state = MagicMock()
    label = bind_mg_client_from_header(request)
    assert label == "chrome-extension"
    assert getattr(request.state, REQUEST_STATE_MG_CLIENT) == "chrome-extension"


def test_bind_web_session() -> None:
    """JWT/cookie sessions bind as web."""
    request = MagicMock()
    request.state = MagicMock()
    assert bind_mg_client_for_web(request) == MG_CLIENT_WEB
    assert getattr(request.state, REQUEST_STATE_MG_CLIENT) == MG_CLIENT_WEB


def test_activity_details_merge_client_source() -> None:
    """Activity details pick up bound client_source without clobbering keys."""
    request = MagicMock()
    request.headers = {}
    request.state = MagicMock()
    setattr(request.state, REQUEST_STATE_MG_CLIENT, "openclaw")
    details = activity_details_with_request_client({"diagram_type": "mind_map"}, request)
    assert details["diagram_type"] == "mind_map"
    assert details["client_source"] == "openclaw"
    assert client_source_from_request(request) == "openclaw"


def test_display_labels() -> None:
    """Known clients have friendly display names."""
    assert mg_client_display_label("chrome-extension") == "Chrome extension"
    assert mg_client_display_label("openclaw") == "OpenClaw"
    assert mg_client_display_label("custom-bot") == "custom-bot"
