"""Tests for client IP resolution behind reverse proxies."""

from typing import cast
from unittest.mock import patch

from utils.auth import request_helpers
from utils.auth.connection_types import HttpOrWebSocket


class _FakeClient:
    def __init__(self, host: str) -> None:
        self.host = host


class _FakeConnection:
    def __init__(self, host: str, headers: dict[str, str] | None = None) -> None:
        self.client = _FakeClient(host)
        self.headers = headers or {}


def test_get_client_ip_ignores_forwarded_headers_without_trusted_proxy() -> None:
    """Untrusted peer: forwarded headers are ignored, direct IP is used."""
    conn = _FakeConnection(
        "203.0.113.10",
        {"X-Forwarded-For": "198.51.100.1", "X-Real-IP": "198.51.100.2"},
    )
    with patch.object(request_helpers, "TRUSTED_PROXY_IPS", []):
        assert request_helpers.get_client_ip(cast(HttpOrWebSocket, conn)) == "203.0.113.10"


def test_get_client_ip_honors_x_forwarded_for_from_trusted_proxy() -> None:
    """Trusted proxy: leftmost X-Forwarded-For entry is the client IP."""
    conn = _FakeConnection(
        "127.0.0.1",
        {"X-Forwarded-For": "198.51.100.1, 10.0.0.1"},
    )
    with patch.object(request_helpers, "TRUSTED_PROXY_IPS", ["127.0.0.1"]):
        assert request_helpers.get_client_ip(cast(HttpOrWebSocket, conn)) == "198.51.100.1"


def test_get_client_ip_falls_back_to_x_real_ip_from_trusted_proxy() -> None:
    """Trusted proxy with no X-Forwarded-For falls back to X-Real-IP."""
    conn = _FakeConnection("127.0.0.1", {"X-Real-IP": "198.51.100.5"})
    with patch.object(request_helpers, "TRUSTED_PROXY_IPS", ["127.0.0.1"]):
        assert request_helpers.get_client_ip(cast(HttpOrWebSocket, conn)) == "198.51.100.5"


def test_get_client_ip_trusts_docker_peer_via_private_keyword() -> None:
    """NPM/Docker bridge peer (172.18.x) is trusted by the ``private`` keyword."""
    conn = _FakeConnection("172.18.0.5", {"X-Forwarded-For": "198.51.100.1"})
    with patch.object(request_helpers, "TRUSTED_PROXY_IPS", ["private"]):
        assert request_helpers.get_client_ip(cast(HttpOrWebSocket, conn)) == "198.51.100.1"


def test_private_keyword_does_not_trust_public_peer() -> None:
    """``private`` must not trust a public peer (no header spoofing from the internet)."""
    conn = _FakeConnection("203.0.113.10", {"X-Forwarded-For": "198.51.100.1"})
    with patch.object(request_helpers, "TRUSTED_PROXY_IPS", ["private"]):
        assert request_helpers.get_client_ip(cast(HttpOrWebSocket, conn)) == "203.0.113.10"


def test_get_client_ip_trusts_cidr_range() -> None:
    """A CIDR entry trusts any peer inside that range."""
    conn = _FakeConnection("10.8.0.3", {"X-Forwarded-For": "198.51.100.7"})
    with patch.object(request_helpers, "TRUSTED_PROXY_IPS", ["10.0.0.0/8"]):
        assert request_helpers.get_client_ip(cast(HttpOrWebSocket, conn)) == "198.51.100.7"


def test_loopback_keyword_excludes_private_lan() -> None:
    """``loopback`` trusts only loopback, not Docker/LAN private ranges."""
    conn = _FakeConnection("172.18.0.5", {"X-Forwarded-For": "198.51.100.1"})
    with patch.object(request_helpers, "TRUSTED_PROXY_IPS", ["loopback"]):
        assert request_helpers.get_client_ip(cast(HttpOrWebSocket, conn)) == "172.18.0.5"
