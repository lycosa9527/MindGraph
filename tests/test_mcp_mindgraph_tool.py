"""Unit tests for MCP tool header building and internal URL guards."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import patch

import pytest
from mcp.server.mcpserver import Context

from services.mcp import mindgraph_mcp as mcp_mod

_internal_base_url = getattr(mcp_mod, "_internal_base_url")
_auth_headers_from_context = getattr(mcp_mod, "_auth_headers_from_context")


def _ctx_with_headers(headers: dict[str, str]) -> Context:
    """Test double for Streamable HTTP request context (headers only)."""
    return cast(Context, SimpleNamespace(headers=headers))


def test_internal_base_url_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unset override uses loopback host and configured port."""
    monkeypatch.delenv("MCP_HTTP_INTERNAL_BASE_URL", raising=False)
    with patch("services.mcp.mindgraph_mcp.config", SimpleNamespace(port=9527)):
        assert _internal_base_url() == "http://127.0.0.1:9527"


def test_internal_base_url_accepts_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Loopback override is accepted and trailing slash stripped."""
    monkeypatch.setenv("MCP_HTTP_INTERNAL_BASE_URL", "http://localhost:9999/")
    assert _internal_base_url() == "http://localhost:9999"


def test_internal_base_url_rejects_non_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-loopback override is ignored (SSRF guard)."""
    monkeypatch.setenv("MCP_HTTP_INTERNAL_BASE_URL", "https://evil.example.com")
    with patch("services.mcp.mindgraph_mcp.config", SimpleNamespace(port=9527)):
        assert _internal_base_url() == "http://127.0.0.1:9527"


def test_auth_headers_require_mgat() -> None:
    """Bearer token must use the mgat_ prefix."""
    ctx = _ctx_with_headers(
        {
            "Authorization": "Bearer not-mgat",
            "X-MG-Account": "17801353751",
        }
    )
    with pytest.raises(ValueError, match="mgat_"):
        _auth_headers_from_context(ctx)


def test_auth_headers_require_account() -> None:
    """X-MG-Account is required alongside a valid mgat_ bearer."""
    ctx = _ctx_with_headers(
        {
            "Authorization": "Bearer mgat_abc",
        }
    )
    with pytest.raises(ValueError, match="X-MG-Account"):
        _auth_headers_from_context(ctx)


def test_auth_headers_forward_request_id_and_client() -> None:
    """Request-id and client labels forward; spoofable proxy headers do not."""
    ctx = _ctx_with_headers(
        {
            "Authorization": "Bearer mgat_abc",
            "X-MG-Account": "17801353751",
            "X-MG-Client": "openclaw",
            "X-Request-Id": "req-1",
        }
    )
    headers = cast(dict[str, Any], _auth_headers_from_context(ctx))
    assert headers["Authorization"] == "Bearer mgat_abc"
    assert headers["X-MG-Account"] == "17801353751"
    assert headers["X-MG-Client"] == "openclaw"
    assert headers["X-Request-Id"] == "req-1"
    assert "X-Forwarded-For" not in headers
    assert "X-Real-IP" not in headers


def test_auth_headers_default_mg_client_and_request_id() -> None:
    """Missing client/request-id headers get mcp default and a generated id."""
    ctx = _ctx_with_headers(
        {
            "authorization": "Bearer mgat_abc",
            "x-mg-account": "17801353751",
        }
    )
    headers = cast(dict[str, Any], _auth_headers_from_context(ctx))
    assert headers["X-MG-Client"] == "mcp"
    assert headers["X-Request-Id"]


def test_build_mindgraph_mcp_singleton() -> None:
    """get_mindgraph_mcp returns a process-wide singleton server."""
    first = mcp_mod.get_mindgraph_mcp()
    second = mcp_mod.get_mindgraph_mcp()
    assert first is second
