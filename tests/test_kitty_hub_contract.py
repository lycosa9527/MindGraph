"""Hub session contract and Kitty bootstrap ordering tests."""

from __future__ import annotations

import sys
import types
from unittest.mock import AsyncMock, patch

import pytest

# ``ws_metrics`` imports ``services.online_collab.redis.redis8_features``. The package
# initializer pulls many online-collab modules and creates a test-only circular import.
# Stub the redis8_features branch so agent-hub tests stay focused and isolated.
online_collab_pkg = types.ModuleType("services.online_collab")
online_collab_pkg.__path__ = []  # type: ignore[attr-defined]
online_collab_redis_pkg = types.ModuleType("services.online_collab.redis")
online_collab_redis_pkg.__path__ = []  # type: ignore[attr-defined]
redis8_features_stub = types.ModuleType("services.online_collab.redis.redis8_features")
redis8_features_stub.timeseries_enabled = lambda: False


async def _ts_record_counter(_key: str, _delta: float) -> None:
    return None


redis8_features_stub.ts_record_counter = _ts_record_counter
sys.modules.setdefault("services.online_collab", online_collab_pkg)
sys.modules.setdefault("services.online_collab.redis", online_collab_redis_pkg)
sys.modules.setdefault("services.online_collab.redis.redis8_features", redis8_features_stub)

from services.agent_hub.scope_lifecycle import MindGraphAgentHub
from services.kitty.kitty_context_hydrate import resolve_mobile_open_bootstrap


@pytest.mark.asyncio
async def test_resolve_mobile_bootstrap_prefers_fresher_focus_scope() -> None:
    """Desktop focus wins when suggested scope metadata is older."""
    with (
        patch(
            "services.kitty.kitty_context_hydrate.get_kitty_desktop_focus_diagram",
            AsyncMock(return_value=("focus_scope", 200)),
        ),
        patch(
            "services.kitty.kitty_context_hydrate.fetch_kitty_sessionmeta_for_user",
            AsyncMock(
                side_effect=[
                    {"updated_at": 100},
                    {"updated_at": 200},
                ]
            ),
        ),
        patch(
            "services.kitty.kitty_context_hydrate.try_build_context_from_live_spec",
            AsyncMock(
                side_effect=[
                    (
                        {"diagram_data": {"children": [{"id": "a"}]}},
                        "circle_map",
                        "none",
                    ),
                    None,
                ]
            ),
        ) as try_live,
    ):
        out = await resolve_mobile_open_bootstrap(1, client_suggested_scope="stale_scope")

    assert out["source"] == "live"
    assert out["recommended_scope"] == "focus_scope"
    assert try_live.await_args_list[0].args[0] == "focus_scope"


@pytest.mark.asyncio
async def test_hub_mutation_idempotency_and_revision_guard() -> None:
    """Repeated idempotency key replays result; stale revision is rejected."""
    hub = MindGraphAgentHub()
    sid = await hub.open_session(99, client_lane="mobile", source_module="kitty_test")
    await hub.bind_scope(sid, diagram_scope="scope_abc", source_module="kitty_test")

    with patch(
        "services.agent_hub.scope_lifecycle.upsert_kitty_redis_session",
        AsyncMock(return_value=123456),
    ):
        first = await hub.apply_diagram_spec_mutation(
            hub_session_id=sid,
            diagram_scope="scope_abc",
            mutation_cmd={
                "op": "replace_context",
                "context": {
                    "diagram_data": {"children": [{"id": "n1", "text": "hello"}]},
                    "diagram_library_id": "scope_abc",
                    "selected_nodes": [],
                },
                "diagram_type": "circle_map",
                "active_panel": "none",
            },
            source_module="kitty_test",
            expected_revision=0,
            idempotency_key="idem-1",
        )
        second = await hub.apply_diagram_spec_mutation(
            hub_session_id=sid,
            diagram_scope="scope_abc",
            mutation_cmd={
                "op": "replace_context",
                "context": {
                    "diagram_data": {"children": [{"id": "n1", "text": "hello"}]},
                },
            },
            source_module="kitty_test",
            expected_revision=0,
            idempotency_key="idem-1",
        )

    assert first["ok"] is True
    assert first["revision"] == 1
    assert second["trace"]["mutation_id"] == first["trace"]["mutation_id"]

    with pytest.raises(ValueError, match="stale expected revision"):
        await hub.apply_diagram_spec_mutation(
            hub_session_id=sid,
            diagram_scope="scope_abc",
            mutation_cmd={"op": "replace_context", "context": {"diagram_data": {}}},
            source_module="kitty_test",
            expected_revision=0,
            idempotency_key="idem-2",
        )
