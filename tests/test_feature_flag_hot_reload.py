"""
Regression tests for admin feature hot on/off.

Covers feature_flag_gate prefixes, workshop WS await on org-access, env reload
fan-out origin skip, and MindMate collab feature key mapping.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.requests import Request

from services.infrastructure.http.feature_gate import feature_flag_gate
from services.infrastructure.sync.env_reload_fanout import handle_env_reload_message
from utils.auth.roles import FEATURE_KEY_TO_CONFIG_ATTR, FEATURE_KEYS_WITH_ORG_ACCESS


def _request(path: str, method: str = "GET") -> Request:
    """Build a minimal ASGI request for the feature gate."""
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
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
async def test_feature_flag_gate_blocks_markets_when_disabled():
    """Hot-off markets via gate without per-route Depends."""
    call_next = AsyncMock(return_value=MagicMock(status_code=200))
    with patch(
        "services.infrastructure.http.feature_gate.config",
        SimpleNamespace(FEATURE_MARKETS=False),
    ):
        response = await feature_flag_gate(_request("/api/markets/listings"), call_next)
    assert response.status_code == 404
    call_next.assert_not_awaited()


@pytest.mark.asyncio
async def test_feature_flag_gate_allows_markets_when_enabled():
    """Markets requests pass through when FEATURE_MARKETS is on."""
    downstream = MagicMock(status_code=200)
    call_next = AsyncMock(return_value=downstream)
    with patch(
        "services.infrastructure.http.feature_gate.config",
        SimpleNamespace(FEATURE_MARKETS=True),
    ):
        response = await feature_flag_gate(_request("/api/markets/listings"), call_next)
    assert response is downstream
    call_next.assert_awaited_once()


@pytest.mark.asyncio
async def test_feature_flag_gate_blocks_workshop_ws_prefix():
    """Workshop chat WebSocket HTTP upgrade path is gated."""
    call_next = AsyncMock(return_value=MagicMock(status_code=200))
    with patch(
        "services.infrastructure.http.feature_gate.config",
        SimpleNamespace(FEATURE_WORKSHOP_CHAT=False),
    ):
        response = await feature_flag_gate(_request("/api/ws/chat"), call_next)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_feature_flag_gate_blocks_kitty_prefix():
    """Kitty REST is gated when FEATURE_KITTY_AGENT is off."""
    call_next = AsyncMock(return_value=MagicMock(status_code=200))
    with patch(
        "services.infrastructure.http.feature_gate.config",
        SimpleNamespace(FEATURE_KITTY_AGENT=False),
    ):
        response = await feature_flag_gate(_request("/api/kitty/session/x"), call_next)
    assert response.status_code == 404


def test_mindmate_collab_feature_key_mapped_and_permissions_supported():
    """Permissions for MindMate collab must resolve FEATURE_MINDMATE_COLLAB."""
    assert FEATURE_KEY_TO_CONFIG_ATTR["feature_mindmate_collab"] == "FEATURE_MINDMATE_COLLAB"
    assert "feature_mindmate_collab" in FEATURE_KEYS_WITH_ORG_ACCESS


def test_workshop_ws_awaits_can_access_workshop_chat():
    """Source must await the async org-access helper (not treat the coroutine as truthy)."""
    source = Path("routers/features/workshop_chat/ws.py").read_text(encoding="utf-8")
    assert "await can_access_workshop_chat(user)" in source
    assert "if not can_access_workshop_chat(user):" not in source


@pytest.mark.asyncio
async def test_env_reload_fanout_skips_same_origin():
    """Publisher worker must not reload twice from its own fan-out message."""
    with patch(
        "services.infrastructure.sync.env_reload_fanout.reload_runtime_config_from_dotenv"
    ) as reload_mock:
        await handle_env_reload_message(
            '{"v":1,"origin":"worker-a"}',
            "worker-a",
        )
        reload_mock.assert_not_called()


@pytest.mark.asyncio
async def test_env_reload_fanout_applies_for_other_origin():
    """Sibling workers reload when they receive another origin's message."""
    with patch(
        "services.infrastructure.sync.env_reload_fanout.reload_runtime_config_from_dotenv"
    ) as reload_mock:
        await handle_env_reload_message(
            '{"v":1,"origin":"worker-a"}',
            "worker-b",
        )
        reload_mock.assert_called_once()
