"""Tests for Dify app API reachability (admin probe)."""

from __future__ import annotations

import pytest

from services.mindbot.dify.service_health import check_dify_app_api_reachable


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
