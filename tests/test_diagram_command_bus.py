"""Tests for DiagramCommandBus (agent_hub diagram_spine)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.agent_hub.diagram_spine.bus import DiagramCommandBus
from services.agent_hub.diagram_spine.origins import DiagramCommandOrigin
from services.agent_hub.diagram_spine.policy import KittyDiagramCommandPolicy
from services.agent_hub.diagram_spine.types import DiagramCommandRequest
from services.diagram_edit.pending import reset_pending_state_for_tests
from services.diagram_edit.types import ToolResult
from services.kitty.session.runtime_state import voice_sessions


class _FakeTransport:
    """In-memory transport for bus tests."""

    def __init__(self, live: dict | None) -> None:
        self._live = live

    def get_live_session(self, voice_session_id: str) -> dict | None:
        """Return the fake live session row."""
        _ = voice_session_id
        return self._live

    def get_hub_revision(self, voice_session_id: str) -> int | None:
        """Return cached hub revision from the fake session."""
        _ = voice_session_id
        if self._live is None:
            return None
        rev = self._live.get("_hub_scope_revision")
        return rev if isinstance(rev, int) else None

    def set_hub_revision(self, voice_session_id: str, revision: int) -> None:
        """Update cached hub revision on the fake session."""
        _ = voice_session_id
        if self._live is not None:
            self._live["_hub_scope_revision"] = revision

    def stash_outbound_extras(self, voice_session_id: str, extras: dict) -> None:
        """Stash outbound extras on the fake session."""
        _ = voice_session_id
        if self._live is not None:
            self._live["_diagram_edit_ws_outbound_extras"] = dict(extras)

    def pop_outbound_extras(self, voice_session_id: str) -> dict | None:
        """Pop and return stashed outbound extras."""
        _ = voice_session_id
        if self._live is None:
            return None
        raw = self._live.pop("_diagram_edit_ws_outbound_extras", None)
        return raw if isinstance(raw, dict) else None


@pytest.mark.asyncio
async def test_bus_policy_rejects_missing_scope() -> None:
    """Bus returns rejected when scope is empty."""
    reset_pending_state_for_tests()
    ws = MagicMock()
    vid = "bus-test-no-scope"
    live = {"diagram_session_id": "", "_hub_scope_revision": 0, "context": {}}
    bus = DiagramCommandBus(policy=KittyDiagramCommandPolicy(), transport=_FakeTransport(live))

    request = DiagramCommandRequest(
        voice_session_id=vid,
        legacy_command={"action": "add_node", "target": "DIY"},
        session_context={},
        scope="",
        diagram_type="mindmap",
        user_id=1,
    )
    result = await bus.apply(ws, request)
    assert result.tool_result.status == "rejected"
    assert result.tool_result.error_code == "no_owner"


@pytest.mark.asyncio
async def test_bus_passes_idempotency_key_to_executor() -> None:
    """Bus forwards idempotency_key into DiagramEditCommand for executor replay."""
    reset_pending_state_for_tests()
    ws = MagicMock()
    live = {
        "diagram_session_id": "scope-1",
        "_hub_scope_revision": 1,
        "context": {"diagram_data": {"children": []}},
    }
    applied = ToolResult(status="applied", mutation_id="cached-mid", revision=2)
    bus = DiagramCommandBus(policy=KittyDiagramCommandPolicy(), transport=_FakeTransport(live))

    request = DiagramCommandRequest(
        voice_session_id="bus-test-idem",
        legacy_command={"action": "add_node", "target": "DIY"},
        session_context=live["context"],
        scope="scope-1",
        diagram_type="mindmap",
        user_id=1,
        idempotency_key="idem-abc",
    )

    with (
        patch(
            "services.agent_hub.diagram_spine.bus.execute_diagram_edit",
            new=AsyncMock(return_value=applied),
        ) as exec_mock,
        patch(
            "services.kitty.infra.scope.kitty_scope_access.user_may_access_kitty_scope",
            new=AsyncMock(return_value=True),
        ),
    ):
        result = await bus.apply(ws, request)

    exec_mock.assert_awaited_once()
    assert exec_mock.await_args is not None
    cmd = exec_mock.await_args.args[2]
    assert cmd.idempotency_key == "idem-abc"
    assert result.tool_result.mutation_id == "cached-mid"
    reset_pending_state_for_tests()


@pytest.mark.asyncio
async def test_bus_verify_required_calls_executor_with_hub_persist() -> None:
    """Verified path requires hub persist on executor."""
    reset_pending_state_for_tests()
    ws = MagicMock()
    vid = "bus-test-verify"
    live = {
        "diagram_session_id": "scope-v",
        "_hub_scope_revision": 3,
        "context": {"diagram_data": {"children": []}, "one_sentence_phase": "edit"},
    }
    applied = ToolResult(status="applied", mutation_id="mid-1", revision=4)
    bus = DiagramCommandBus(policy=KittyDiagramCommandPolicy(), transport=_FakeTransport(live))

    request = DiagramCommandRequest(
        voice_session_id=vid,
        legacy_command={"action": "add_node", "target": "DIY"},
        session_context=live["context"],
        scope="scope-v",
        diagram_type="mindmap",
        user_id=1,
        verify_required=True,
        origin=DiagramCommandOrigin.KITTY_MOBILE,
    )

    with (
        patch(
            "services.agent_hub.diagram_spine.bus.execute_diagram_edit",
            new=AsyncMock(return_value=applied),
        ) as exec_mock,
        patch(
            "services.kitty.infra.scope.kitty_scope_access.user_may_access_kitty_scope",
            new=AsyncMock(return_value=True),
        ),
    ):
        result = await bus.apply(ws, request)

    exec_mock.assert_awaited_once()
    assert exec_mock.await_args is not None
    call_kwargs = exec_mock.await_args.kwargs
    assert call_kwargs["verify_required"] is True
    assert call_kwargs["require_hub_persist"] is True
    assert result.hub_revision == 4
    assert result.origin == DiagramCommandOrigin.KITTY_MOBILE


@pytest.mark.asyncio
async def test_bus_legacy_non_verified_skips_hub_persist() -> None:
    """Legacy voice path uses verify_required=false and diagram_execute."""
    reset_pending_state_for_tests()
    ws = MagicMock()
    vid = "bus-test-legacy"
    voice_sessions[vid] = {
        "diagram_session_id": "scope-l",
        "_hub_scope_revision": 0,
        "context": {"diagram_data": {"children": []}},
    }

    try:
        bus = DiagramCommandBus()
        request = DiagramCommandRequest(
            voice_session_id=vid,
            legacy_command={"action": "add_node", "target": "X"},
            session_context=voice_sessions[vid]["context"],
            scope="scope-l",
            diagram_type="circle_map",
            verify_required=False,
        )
        with (
            patch.object(
                DiagramCommandBus,
                "_apply_legacy_voice",
                new=AsyncMock(return_value=ToolResult(status="applied", mutation_id="mid-legacy", revision=0)),
            ) as legacy_mock,
            patch(
                "services.kitty.infra.scope.kitty_scope_access.user_may_access_kitty_scope",
                new=AsyncMock(return_value=True),
            ),
            patch(
                "services.agent_hub.diagram_spine.bus.execute_diagram_edit",
                new=AsyncMock(),
            ) as exec_mock,
        ):
            result = await bus.apply(ws, request)

        legacy_mock.assert_awaited_once()
        exec_mock.assert_not_awaited()
        assert result.applied is True
    finally:
        voice_sessions.pop(vid, None)
        reset_pending_state_for_tests()
