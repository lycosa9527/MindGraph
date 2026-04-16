"""Tests for Dify app API reachability (admin probe)."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from services.mindbot.dify.service_health import check_dify_app_api_reachable


def _make_mock_session(status: int, body: str = "") -> MagicMock:
    """Build a mock aiohttp session whose GET returns the given status and body."""
    mock_resp = MagicMock()
    mock_resp.status = status
    mock_resp.read = AsyncMock(return_value=b"")
    mock_resp.text = AsyncMock(return_value=body)

    @asynccontextmanager
    async def _fake_get(*_args: Any, **_kwargs: Any):
        yield mock_resp

    mock_session = MagicMock()
    mock_session.get = _fake_get
    return mock_session


@pytest.mark.asyncio
async def test_empty_key_returns_not_configured() -> None:
    ok, status, err = await check_dify_app_api_reachable(
        "https://example.com/v1",
        "",
    )
    assert ok is False
    assert status is None
    assert err == "api_key_not_configured"


@pytest.mark.asyncio
async def test_empty_base_returns_not_configured() -> None:
    ok, status, err = await check_dify_app_api_reachable(
        "",
        "app-xxx",
    )
    assert ok is False
    assert status is None
    assert err == "base_url_not_configured"


@pytest.mark.asyncio
async def test_http_200_returns_online() -> None:
    mock_session = _make_mock_session(status=200)
    with patch("services.mindbot.dify.service_health.get_outbound_session", return_value=mock_session):
        ok, status, err = await check_dify_app_api_reachable(
            "https://dify.example.com/v1",
            "app-key-123",
        )
    assert ok is True
    assert status == 200
    assert err is None


@pytest.mark.asyncio
async def test_http_403_returns_offline_with_status() -> None:
    mock_session = _make_mock_session(status=403, body="Forbidden")
    with patch("services.mindbot.dify.service_health.get_outbound_session", return_value=mock_session):
        ok, status, err = await check_dify_app_api_reachable(
            "https://dify.example.com/v1",
            "app-key-123",
        )
    assert ok is False
    assert status == 403
    assert err is not None
    assert "403" in err


@pytest.mark.asyncio
async def test_timeout_returns_timeout_error() -> None:
    mock_session = MagicMock()
    mock_session.get = MagicMock(side_effect=asyncio.TimeoutError)
    with patch("services.mindbot.dify.service_health.get_outbound_session", return_value=mock_session):
        ok, status, err = await check_dify_app_api_reachable(
            "https://dify.example.com/v1",
            "app-key-123",
        )
    assert ok is False
    assert status is None
    assert err == "timeout"


@pytest.mark.asyncio
async def test_client_error_returns_error_string() -> None:
    mock_session = MagicMock()
    mock_session.get = MagicMock(side_effect=aiohttp.ClientConnectionError("connection refused"))
    with patch("services.mindbot.dify.service_health.get_outbound_session", return_value=mock_session):
        ok, status, err = await check_dify_app_api_reachable(
            "https://dify.example.com/v1",
            "app-key-123",
        )
    assert ok is False
    assert status is None
    assert err is not None
    assert len(err) > 0
