"""Maite feature gate and ownership helpers."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.requests import Request

from services.infrastructure.http.feature_gate import feature_flag_gate
from utils.auth.roles import FEATURE_KEY_TO_CONFIG_ATTR


def _request(path: str) -> Request:
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("ascii"),
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 12345),
        "server": ("test", 80),
    }
    return Request(scope)


@pytest.mark.asyncio
async def test_feature_flag_gate_blocks_maite_when_disabled():
    """Hot-off maite via gate."""
    call_next = AsyncMock(return_value=MagicMock(status_code=200))
    with patch(
        "services.infrastructure.http.feature_gate.config",
        SimpleNamespace(FEATURE_MATE_LEARNING=False),
    ):
        response = await feature_flag_gate(_request("/api/maite/health"), call_next)
    assert response.status_code == 404
    call_next.assert_not_awaited()


@pytest.mark.asyncio
async def test_feature_flag_gate_allows_maite_when_enabled():
    """Mate Learning requests pass when FEATURE_MATE_LEARNING is on."""
    downstream = MagicMock(status_code=200)
    call_next = AsyncMock(return_value=downstream)
    with patch(
        "services.infrastructure.http.feature_gate.config",
        SimpleNamespace(FEATURE_MATE_LEARNING=True),
    ):
        response = await feature_flag_gate(_request("/api/maite/inquiry/sessions"), call_next)
    assert response is downstream
    call_next.assert_awaited_once()


def test_maite_feature_key_mapped():
    """Admin/org-access map includes maite learning."""
    assert FEATURE_KEY_TO_CONFIG_ATTR["feature_mate_learning"] == "FEATURE_MATE_LEARNING"
