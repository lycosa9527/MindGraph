"""Tests for MCP mgat_ transport auth and rate limiting."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from services.mcp.auth_middleware import McpMgatAuthMiddleware


async def _ok(_request: Request) -> PlainTextResponse:
    return PlainTextResponse("ok")


def _app() -> TestClient:
    inner = Starlette(routes=[Route("/", endpoint=_ok, methods=["GET", "POST", "DELETE", "OPTIONS"])])
    return TestClient(McpMgatAuthMiddleware(inner))


def test_mcp_auth_missing_bearer_returns_401() -> None:
    """POST without Authorization is rejected before the inner app."""
    client = _app()
    response = client.post("/", headers={"X-MG-Account": "17801353751"})
    assert response.status_code == 401
    assert "mgat_" in response.json()["detail"]


def test_mcp_auth_non_mgat_bearer_returns_401() -> None:
    """Non-mgat_ bearer tokens are rejected at the MCP transport layer."""
    client = _app()
    response = client.post(
        "/",
        headers={
            "Authorization": "Bearer jwt-not-mgat",
            "X-MG-Account": "17801353751",
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_mcp_auth_valid_token_reaches_inner() -> None:
    """Valid mgat_ token + account reaches the inner app and rate-limit check."""
    user = SimpleNamespace(id=3)
    with (
        patch(
            "services.mcp.auth_middleware.validate_user_token",
            new=AsyncMock(return_value=user),
        ),
        patch(
            "services.mcp.auth_middleware._check_mcp_rate_limit",
            new=AsyncMock(),
        ) as rate_limit,
    ):
        client = _app()
        response = client.post(
            "/",
            headers={
                "Authorization": "Bearer mgat_testtoken",
                "X-MG-Account": "17801353751",
            },
        )
    assert response.status_code == 200
    assert response.text == "ok"
    rate_limit.assert_awaited_once_with(3)


def test_mcp_auth_invalid_token_maps_http_exception() -> None:
    """Token validation HTTPException status/detail are preserved."""
    with patch(
        "services.mcp.auth_middleware.validate_user_token",
        new=AsyncMock(side_effect=HTTPException(status_code=401, detail="Invalid or expired token")),
    ):
        client = _app()
        response = client.post(
            "/",
            headers={
                "Authorization": "Bearer mgat_bad",
                "X-MG-Account": "17801353751",
            },
        )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired token"


def test_mcp_auth_rate_limit_returns_429() -> None:
    """Per-user rate-limit HTTPException becomes 429 at the transport layer."""
    user = SimpleNamespace(id=9)
    with (
        patch(
            "services.mcp.auth_middleware.validate_user_token",
            new=AsyncMock(return_value=user),
        ),
        patch(
            "services.mcp.auth_middleware._check_mcp_rate_limit",
            new=AsyncMock(side_effect=HTTPException(status_code=429, detail="Too many requests.")),
        ),
    ):
        client = _app()
        response = client.post(
            "/",
            headers={
                "Authorization": "Bearer mgat_ok",
                "X-MG-Account": "17801353751",
            },
        )
    assert response.status_code == 429


def test_mcp_auth_options_passes_without_token() -> None:
    """CORS preflight OPTIONS is allowed without mgat_ credentials."""
    client = _app()
    response = client.options("/")
    assert response.status_code == 200
