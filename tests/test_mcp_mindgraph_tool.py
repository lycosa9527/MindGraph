"""Unit tests for MCP tool header building and internal URL guards."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from services.mcp import mindgraph_mcp as mcp_mod


def test_internal_base_url_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MCP_HTTP_INTERNAL_BASE_URL", raising=False)
    with patch("services.mcp.mindgraph_mcp.config", SimpleNamespace(port=9527)):
        assert mcp_mod._internal_base_url() == "http://127.0.0.1:9527"


def test_internal_base_url_accepts_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP_HTTP_INTERNAL_BASE_URL", "http://localhost:9999/")
    assert mcp_mod._internal_base_url() == "http://localhost:9999"


def test_internal_base_url_rejects_non_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP_HTTP_INTERNAL_BASE_URL", "https://evil.example.com")
    with patch("services.mcp.mindgraph_mcp.config", SimpleNamespace(port=9527)):
        assert mcp_mod._internal_base_url() == "http://127.0.0.1:9527"


def test_auth_headers_require_mgat() -> None:
    ctx = SimpleNamespace(
        headers={
            "Authorization": "Bearer not-mgat",
            "X-MG-Account": "17801353751",
        }
    )
    with pytest.raises(ValueError, match="mgat_"):
        mcp_mod._auth_headers_from_context(ctx)


def test_auth_headers_require_account() -> None:
    ctx = SimpleNamespace(
        headers={
            "Authorization": "Bearer mgat_abc",
        }
    )
    with pytest.raises(ValueError, match="X-MG-Account"):
        mcp_mod._auth_headers_from_context(ctx)


def test_auth_headers_forward_request_id_and_client() -> None:
    ctx = SimpleNamespace(
        headers={
            "Authorization": "Bearer mgat_abc",
            "X-MG-Account": "17801353751",
            "X-MG-Client": "openclaw",
            "X-Request-Id": "req-1",
        }
    )
    headers = mcp_mod._auth_headers_from_context(ctx)
    assert headers["Authorization"] == "Bearer mgat_abc"
    assert headers["X-MG-Account"] == "17801353751"
    assert headers["X-MG-Client"] == "openclaw"
    assert headers["X-Request-Id"] == "req-1"
    assert "X-Forwarded-For" not in headers
    assert "X-Real-IP" not in headers


def test_auth_headers_default_mg_client_and_request_id() -> None:
    ctx = SimpleNamespace(
        headers={
            "authorization": "Bearer mgat_abc",
            "x-mg-account": "17801353751",
        }
    )
    headers = mcp_mod._auth_headers_from_context(ctx)
    assert headers["X-MG-Client"] == "mcp"
    assert headers["X-Request-Id"]


def test_build_mindgraph_mcp_singleton() -> None:
    first = mcp_mod.get_mindgraph_mcp()
    second = mcp_mod.get_mindgraph_mcp()
    assert first is second
