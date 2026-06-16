"""Hub session contract and Kitty bootstrap ordering tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from tests.stubs.redis8_features import install_redis8_features_stub

install_redis8_features_stub()

from tests.typing_helpers import mock_await_kwargs
from services.agent_hub.scope_lifecycle import MindGraphAgentHub
from services.kitty.infra.bootstrap.kitty_context_hydrate import resolve_mobile_open_bootstrap


@pytest.mark.asyncio
async def test_resolve_mobile_bootstrap_prefers_fresher_focus_scope() -> None:
    """Desktop focus wins when suggested scope metadata is older."""
    with (
        patch(
            "services.kitty.infra.bootstrap.kitty_context_hydrate.get_kitty_desktop_focus_diagram",
            AsyncMock(return_value=("focus_scope", 200)),
        ),
        patch(
            "services.kitty.infra.bootstrap.kitty_context_hydrate.fetch_kitty_sessionmeta_for_user",
            AsyncMock(
                side_effect=[
                    {"updated_at": 100},
                    {"updated_at": 200},
                ]
            ),
        ),
        patch(
            "services.kitty.infra.bootstrap.kitty_context_hydrate.try_build_context_from_live_spec",
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


@pytest.mark.asyncio
async def test_hub_persist_library_from_mutation_cmd() -> None:
    """persist_library + library_snapshot saves via diagram cache before live_spec."""
    hub = MindGraphAgentHub()
    sid = await hub.open_session(77, client_lane="mobile", source_module="kitty_test")
    await hub.bind_scope(sid, diagram_scope="lib-persist-1", source_module="kitty_test")

    save_mock = AsyncMock(return_value=(True, "lib-persist-1", None))
    with (
        patch(
            "services.agent_hub.scope_lifecycle.get_diagram_cache",
        ) as cache_factory,
        patch(
            "services.agent_hub.scope_lifecycle.upsert_kitty_redis_session",
            AsyncMock(return_value=999001),
        ),
        patch(
            "services.agent_hub.scope_lifecycle.resolve_mobile_open_bootstrap",
            AsyncMock(return_value={"context": {}, "source": "library"}),
        ),
        patch(
            "services.agent_hub.scope_lifecycle.merge_voice_context_with_library",
            AsyncMock(
                return_value=(
                    {
                        "diagram_library_id": "lib-persist-1",
                        "diagram_data": {"children": []},
                        "selected_nodes": [],
                    },
                    "circle_map",
                    "none",
                )
            ),
        ),
    ):
        cache_factory.return_value.save_diagram = save_mock
        out = await hub.apply_diagram_spec_mutation(
            hub_session_id=sid,
            diagram_scope="lib-persist-1",
            mutation_cmd={
                "op": "patch_context",
                "context": {
                    "diagram_library_id": "lib-persist-1",
                    "diagram_data": {"children": []},
                    "selected_nodes": [],
                },
                "diagram_type": "circle_map",
                "active_panel": "none",
                "persist_library": True,
                "library_snapshot": {
                    "spec": {"nodes": [{"id": "context-0"}], "connections": []},
                    "title": "Voice save",
                    "language": "zh",
                },
            },
            source_module="kitty_test",
            expected_revision=0,
            idempotency_key="persist-1",
        )

    assert out["ok"] is True
    assert out.get("library_snapshot_saved") is True
    save_mock.assert_awaited_once()
    save_args = mock_await_kwargs(save_mock)
    assert save_args["diagram_id"] == "lib-persist-1"
    assert save_args["title"] == "Voice save"
