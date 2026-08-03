"""Tests for MCP host lifespan and /api/mcp trailing-slash normalization."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Mount, Route
from starlette.testclient import TestClient

from services.mcp.mount import EnsureMcpTrailingSlashMiddleware
from services.mcp.mount_state import (
    is_mindgraph_mcp_mounted,
    mark_mindgraph_mcp_mounted,
    reset_mindgraph_mcp_mounted_for_tests,
)
from services.mcp.session_lifespan import mindgraph_mcp_session_run


@pytest.fixture(autouse=True)
def _reset_mount_flag() -> Any:
    reset_mindgraph_mcp_mounted_for_tests()
    yield
    reset_mindgraph_mcp_mounted_for_tests()


@pytest.mark.asyncio
async def test_mcp_session_run_noop_when_not_mounted() -> None:
    async with mindgraph_mcp_session_run():
        pass
    assert is_mindgraph_mcp_mounted() is False


@pytest.mark.asyncio
async def test_mcp_session_run_enters_manager_when_mounted() -> None:
    entered = {"value": False}

    @asynccontextmanager
    async def fake_run() -> Any:
        entered["value"] = True
        yield

    manager = MagicMock()
    manager.run = MagicMock(side_effect=fake_run)
    server = MagicMock()
    server.session_manager = manager
    mark_mindgraph_mcp_mounted()

    with patch(
        "services.mcp.session_lifespan.get_mindgraph_mcp",
        return_value=server,
    ):
        async with mindgraph_mcp_session_run():
            assert entered["value"] is True

    manager.run.assert_called_once_with()


@pytest.mark.asyncio
async def test_mcp_session_run_warns_when_manager_missing() -> None:
    server = MagicMock(spec=[])
    mark_mindgraph_mcp_mounted()
    with (
        patch(
            "services.mcp.session_lifespan.get_mindgraph_mcp",
            return_value=server,
        ),
        patch("services.mcp.session_lifespan.logger") as mock_logger,
    ):
        async with mindgraph_mcp_session_run():
            pass
        mock_logger.warning.assert_called_once()


def test_ensure_mcp_trailing_slash_rewrites_bare_path() -> None:
    async def ok(_request: Request) -> PlainTextResponse:
        return PlainTextResponse("ok")

    inner = Starlette(
        routes=[
            Mount(
                "/api/mcp",
                routes=[Route("/", endpoint=ok, methods=["GET", "POST"])],
            )
        ]
    )
    app = EnsureMcpTrailingSlashMiddleware(inner)
    client = TestClient(app)

    response = client.post("/api/mcp", content=b"{}")
    assert response.status_code == 200
    assert response.text == "ok"


def test_ensure_mcp_trailing_slash_leaves_other_paths() -> None:
    seen: dict[str, str] = {}

    async def capture(request: Request) -> PlainTextResponse:
        seen["path"] = request.url.path
        return PlainTextResponse("ok")

    inner = Starlette(routes=[Route("/api/health", endpoint=capture, methods=["GET"])])
    app = EnsureMcpTrailingSlashMiddleware(inner)
    client = TestClient(app)

    response = client.get("/api/health")
    assert response.status_code == 200
    assert seen["path"] == "/api/health"
