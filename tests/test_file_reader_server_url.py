"""Tests for file-reader server URL allowlist."""

from __future__ import annotations

import pytest

from file_reader.server_url import (
    ServerUrlError,
    normalize_server_url,
    preset_label_for_server_url,
    server_url_from_preset_label,
)


def test_normalize_production_https() -> None:
    """Accept MindGraph production hosts over HTTPS."""
    assert normalize_server_url("https://test.mindspringedu.com") == "https://test.mindspringedu.com"
    assert normalize_server_url("https://mg.mindspringedu.com/") == "https://mg.mindspringedu.com"


def test_normalize_localhost_http() -> None:
    """Allow HTTP only for localhost dev targets."""
    assert normalize_server_url("http://127.0.0.1:9527") == "http://127.0.0.1:9527"
    assert normalize_server_url("http://localhost") == "http://localhost"


def test_reject_plain_http_production() -> None:
    """Reject HTTP for production hosts."""
    with pytest.raises(ServerUrlError):
        normalize_server_url("http://test.mindspringedu.com")


def test_reject_unknown_host() -> None:
    """Reject hosts outside the allowlist."""
    with pytest.raises(ServerUrlError):
        normalize_server_url("https://evil.example.com")


def test_reject_non_default_port_production() -> None:
    """Reject non-443 ports on production hosts."""
    with pytest.raises(ServerUrlError):
        normalize_server_url("https://test.mindspringedu.com:8443")


def test_preset_label_round_trip() -> None:
    """Map preset labels to URLs and back."""
    for label in ("mg.mindspringedu.com", "test.mindspringedu.com", "localhost:9527"):
        url = server_url_from_preset_label(label)
        assert preset_label_for_server_url(url) == label


def test_preset_label_maps_localhost_aliases() -> None:
    """Treat 127.0.0.1:9527 as the localhost preset."""
    assert preset_label_for_server_url("http://127.0.0.1:9527") == "localhost:9527"
