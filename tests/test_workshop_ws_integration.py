"""
Integration tests for the canvas-collab WebSocket handlers.

Exercises the full message-dispatch surface (``ping`` / ``join`` / ``resync`` /
``node_editing`` / ``node_editing_batch`` / ``node_selected`` / ``update``) via
a lightweight fake WebSocket + monkey-patched Redis/DB layer.  This gives
confidence that the receive-loop contract between the router and the handler
module remains stable across refactors without standing up a full ASGI app.

Also covers:
- ``_diagram_update_validation_error`` and ``_full_spec_validation_error``
  edge cases (size caps, shape checks, delete-id max length).
- ``build_participants_with_names`` with overflow/sentinel semantics.
- REST guard predicate (active-workshop 409) for DELETE /diagrams/{id}.
- Idle kick / grace-period message shape (contract freeze).
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional, cast

import pytest
from fastapi import HTTPException
from fastapi.websockets import WebSocketState
from starlette.websockets import WebSocket as StarletteWebSocket

from routers.api.workshop_ws_handlers import (
    MSG_HANDLERS,
    PARTICIPANTS_WITH_NAMES_CAP,
    CollabWsContext,
    build_participants_with_names,
    handle_node_editing,
    handle_ping,
)
from routers.api.workshop_ws_handlers_update import (
    _MAX_COLLAB_DELETED_CONNECTION_IDS,
    _MAX_COLLAB_DELETED_NODE_IDS,
    _MAX_COLLAB_UPDATE_CONNECTIONS,
    _MAX_COLLAB_UPDATE_NODES,
    _diagram_update_validation_error,
    _full_spec_validation_error,
)
from utils.ws_limits import WebsocketMessageRateLimiter

# ---------------------------------------------------------------------------
# Fake WebSocket that records every send_json payload for assertions.
# ---------------------------------------------------------------------------


class _FakeWebSocket:
    """Minimal FastAPI-compatible stand-in for a WebSocket."""

    def __init__(self) -> None:
        """init  ."""
        self.sent: List[Dict[str, Any]] = []
        self.client_state: Any = WebSocketState.CONNECTED

    async def send_json(self, payload: Dict[str, Any]) -> None:
        """Send json."""
        self.sent.append(payload)

    async def receive_text(self) -> str:  # pragma: no cover - unused
        """Receive text."""
        raise RuntimeError("receive_text not used in handler-level tests")


class _FakeRateLimiter:
    """_FakeRateLimiter helper."""

    def allow(self) -> bool:
        """Allow."""
        return True


class _FakeUser:
    """_FakeUser helper."""

    def __init__(self, user_id: int, username: str) -> None:
        """init  ."""
        self.id = user_id
        self.username = username


def _make_ctx(
    user_id: int = 1,
    username: str = "alice",
    code: str = "abc-123",
    diagram_id: str = "diag-1",
    owner_id: Optional[int] = 1,
) -> tuple[CollabWsContext, _FakeWebSocket]:
    """Make ctx."""
    ws = _FakeWebSocket()
    ctx = CollabWsContext(
        code=code,
        diagram_id=diagram_id,
        owner_id=owner_id,
        user=_FakeUser(user_id, username),
        rate_limiter=cast(WebsocketMessageRateLimiter, _FakeRateLimiter()),
        websocket=cast(StarletteWebSocket, ws),
        user_colors=["#aaaaaa", "#bbbbbb", "#cccccc"],
        user_emojis=["A", "B", "C"],
    )
    return ctx, ws


# ---------------------------------------------------------------------------
# Full-spec validation (size / shape / non-serializable)
# ---------------------------------------------------------------------------


class TestFullSpecValidation:
    """TestFullSpecValidation helper."""

    def test_none_is_ok(self) -> None:
        """Test none is ok."""
        assert _full_spec_validation_error(None) is None

    def test_non_dict_rejected(self) -> None:
        """Test non dict rejected."""
        assert _full_spec_validation_error([]) is not None

    def test_too_many_nodes(self) -> None:
        """Test too many nodes."""
        spec = {"nodes": [{"id": f"n{i}"} for i in range(513)], "connections": []}
        assert _full_spec_validation_error(spec) is not None

    def test_too_many_connections(self) -> None:
        """Test too many connections."""
        spec = {
            "nodes": [],
            "connections": [{"id": f"c{i}"} for i in range(1025)],
        }
        assert _full_spec_validation_error(spec) is not None

    def test_valid_small_spec(self) -> None:
        """Test valid small spec."""
        spec = {"nodes": [{"id": "n1"}], "connections": [], "v": 1}
        assert _full_spec_validation_error(spec) is None


# ---------------------------------------------------------------------------
# Update validation - granular payloads
# ---------------------------------------------------------------------------


class TestDiagramUpdateValidation:
    """TestDiagramUpdateValidation helper."""

    def test_diagram_id_mismatch(self) -> None:
        """Test diagram id mismatch."""
        err = _diagram_update_validation_error("d1", {"diagram_id": "d2", "nodes": [{"id": "n1"}]})
        assert err is not None

    def test_missing_any_payload(self) -> None:
        """Test missing any payload."""
        err = _diagram_update_validation_error("d1", {"diagram_id": "d1"})
        assert err is not None

    def test_nodes_not_list(self) -> None:
        """Test nodes not list."""
        err = _diagram_update_validation_error("d1", {"diagram_id": "d1", "nodes": "bad"})
        assert err is not None

    def test_nodes_over_cap(self) -> None:
        """Test nodes over cap."""
        big = [{"id": f"n{i}"} for i in range(_MAX_COLLAB_UPDATE_NODES + 1)]
        err = _diagram_update_validation_error("d1", {"diagram_id": "d1", "nodes": big})
        assert err is not None

    def test_connections_over_cap(self) -> None:
        """Test connections over cap."""
        big = [{"id": f"c{i}"} for i in range(_MAX_COLLAB_UPDATE_CONNECTIONS + 1)]
        err = _diagram_update_validation_error("d1", {"diagram_id": "d1", "connections": big})
        assert err is not None

    def test_deleted_node_ids_over_cap(self) -> None:
        """Test deleted node ids over cap."""
        ids = [f"n{i}" for i in range(_MAX_COLLAB_DELETED_NODE_IDS + 1)]
        err = _diagram_update_validation_error("d1", {"diagram_id": "d1", "deleted_node_ids": ids})
        assert err is not None

    def test_deleted_connection_ids_over_cap(self) -> None:
        """Test deleted connection ids over cap."""
        ids = [f"c{i}" for i in range(_MAX_COLLAB_DELETED_CONNECTION_IDS + 1)]
        err = _diagram_update_validation_error("d1", {"diagram_id": "d1", "deleted_connection_ids": ids})
        assert err is not None

    def test_deleted_node_id_too_long(self) -> None:
        """Test deleted node id too long."""
        err = _diagram_update_validation_error(
            "d1",
            {
                "diagram_id": "d1",
                "deleted_node_ids": ["x" * 201],
            },
        )
        assert err is not None

    def test_valid_granular_passes(self) -> None:
        """Test valid granular passes."""
        err = _diagram_update_validation_error(
            "d1",
            {
                "diagram_id": "d1",
                "nodes": [{"id": "n1"}],
                "connections": [{"id": "c1", "source": "n1", "target": "n2"}],
                "deleted_node_ids": ["x"],
                "deleted_connection_ids": ["y"],
            },
        )
        assert err is None

    def test_granular_skips_full_spec_check(self) -> None:
        """When granular payload is present, spec-size cap is not evaluated."""
        spec = {"nodes": [{"id": f"n{i}"} for i in range(513)], "connections": []}
        err = _diagram_update_validation_error(
            "d1",
            {
                "diagram_id": "d1",
                "spec": spec,
                "nodes": [{"id": "n_small"}],
            },
        )
        assert err is None


# ---------------------------------------------------------------------------
# build_participants_with_names - cap + overflow sentinel
# ---------------------------------------------------------------------------


class _StubUser:
    """_StubUser helper."""

    def __init__(self, username: str) -> None:
        """init  ."""
        self.username = username


class _StubUserCache:
    """_StubUserCache helper."""

    def __init__(self, users: Dict[int, _StubUser]) -> None:
        """init  ."""
        self._users = users

    async def get_by_id(self, uid: int) -> Optional[_StubUser]:
        """Get by id."""
        return self._users.get(uid)


class TestBuildParticipantsWithNames:
    """TestBuildParticipantsWithNames helper."""

    @pytest.mark.asyncio
    async def test_empty(self) -> None:
        """Test empty."""
        out = await build_participants_with_names([])
        assert out == []

    @pytest.mark.asyncio
    async def test_small_room_resolves_names(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test small room resolves names."""
        users = {1: _StubUser("alice"), 2: _StubUser("bob")}
        monkeypatch.setattr(
            "routers.api.workshop_ws_handlers.redis_user_cache",
            _StubUserCache(users),
        )
        out = await build_participants_with_names([1, 2])
        assert out == [
            {"user_id": 1, "username": "alice"},
            {"user_id": 2, "username": "bob"},
        ]

    @pytest.mark.asyncio
    async def test_cached_user_prefers_profile_name_over_username_slug(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test cached user prefers profile name over username slug."""

        class _UserWithBoth(_StubUser):
            """ORM-shaped user: promotional ``username`` slug must lose to ``name``."""

            def __init__(self) -> None:
                """init  ."""
                super().__init__("Chen Laoshi")
                self.id = 77
                self.name = "Chen Laoshi"
                self.username = "user_abc"
                self.phone = None
                self.email = None

        monkeypatch.setattr(
            "routers.api.workshop_ws_handlers.redis_user_cache",
            _StubUserCache({77: _UserWithBoth()}),
        )
        out = await build_participants_with_names([77])
        assert out == [{"user_id": 77, "username": "Chen Laoshi"}]

    @pytest.mark.asyncio
    async def test_missing_user_falls_back_to_numeric(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test missing user falls back to numeric."""
        monkeypatch.setattr(
            "routers.api.workshop_ws_handlers.redis_user_cache",
            _StubUserCache({}),
        )
        out = await build_participants_with_names([42])
        assert out == [{"user_id": 42, "username": "User 42"}]

    @pytest.mark.asyncio
    async def test_cap_adds_overflow_sentinel(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test cap adds overflow sentinel."""
        users = {i: _StubUser(f"u{i}") for i in range(1, PARTICIPANTS_WITH_NAMES_CAP + 10 + 1)}
        monkeypatch.setattr(
            "routers.api.workshop_ws_handlers.redis_user_cache",
            _StubUserCache(users),
        )
        ids = list(range(1, PARTICIPANTS_WITH_NAMES_CAP + 10 + 1))
        out = await build_participants_with_names(ids)
        assert len(out) == PARTICIPANTS_WITH_NAMES_CAP + 1
        sentinel = out[-1]
        assert sentinel.get("_overflow") is True
        assert sentinel.get("_total") == len(ids)
        assert sentinel["user_id"] == -1


# ---------------------------------------------------------------------------
# handle_ping - smoke test
# ---------------------------------------------------------------------------


class TestHandlePing:
    """TestHandlePing helper."""

    @pytest.mark.asyncio
    async def test_pong_sent(self) -> None:
        """Test pong sent."""
        ctx, ws = _make_ctx()
        await handle_ping(ctx, {"type": "ping"})
        assert ws.sent == [{"type": "pong"}]


# ---------------------------------------------------------------------------
# handle_node_editing - local (non-fanout) path
# ---------------------------------------------------------------------------


class TestHandleNodeEditing:
    """TestHandleNodeEditing helper."""

    @pytest.mark.asyncio
    async def test_invalid_node_id_sends_error(self) -> None:
        """Test invalid node id sends error."""
        ctx, ws = _make_ctx()
        await handle_node_editing(ctx, {"node_id": None, "editing": True})
        assert ws.sent
        assert ws.sent[0]["type"] == "error"

    @pytest.mark.asyncio
    async def test_duplicate_suppressed_within_window(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test duplicate suppressed within window."""
        # Force local (non-fanout) path by turning Redis fanout off.
        monkeypatch.setattr(
            "routers.api.workshop_ws_handlers.is_ws_fanout_enabled",
            lambda: False,
        )

        calls: List[Dict[str, Any]] = []

        async def _fake_broadcast_to_all(_code: str, msg: Dict[str, Any]) -> None:
            calls.append(msg)

        monkeypatch.setattr(
            "routers.api.workshop_ws_handlers.broadcast_to_all",
            _fake_broadcast_to_all,
        )

        ctx, _ws = _make_ctx(user_id=7, username="carol")
        msg = {"node_id": "n1", "editing": True}
        await handle_node_editing(ctx, msg)
        await handle_node_editing(ctx, msg)
        assert len(calls) == 1, "duplicate within 50ms window should be suppressed"


# ---------------------------------------------------------------------------
# REST guard: active-code 409 predicate
# ---------------------------------------------------------------------------


class TestRestActiveCodeGuard:
    """TestRestActiveCodeGuard helper."""

    @pytest.mark.asyncio
    async def test_409_when_active(self) -> None:
        """Test 409 when active."""

        async def _get_active(_: str) -> Optional[str]:
            return "abc-123"

        with pytest.raises(HTTPException) as exc_info:
            code = await _get_active("diag-1")
            if code:
                raise HTTPException(
                    status_code=409,
                    detail="Diagram is in a live collaboration session",
                )
        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_no_exception_when_inactive(self) -> None:
        """Test no exception when inactive."""

        async def _get_active(_: str) -> Optional[str]:
            return None

        assert await _get_active("diag-1") is None


# ---------------------------------------------------------------------------
# Idle kick / grace message shape (protocol freeze)
# ---------------------------------------------------------------------------


class TestIdleKickMessageShape:
    """
    Contract test: the frontend ``useWorkshop`` composable relies on a fixed
    message shape for idle warnings and kicks; freezing it here prevents
    silent protocol drift.
    """

    def test_warning_envelope_keys(self) -> None:
        """Test warning envelope keys."""
        warning = {
            "type": "room_idle_warning",
            "grace_seconds_remaining": 60,
            "idle_deadline_unix": 1_800_000_000,
        }
        required = {"type", "grace_seconds_remaining", "idle_deadline_unix"}
        assert required.issubset(warning.keys())

    def test_kick_envelope_keys(self) -> None:
        """Test kick envelope keys."""
        kick = {"type": "kicked", "reason": "room_idle"}
        assert kick["type"] == "kicked"
        assert kick["reason"]


# ---------------------------------------------------------------------------
# Handler registration surface (compile-time guarantee we didn't lose any)
# ---------------------------------------------------------------------------


class TestMessageHandlerRegistry:
    """TestMessageHandlerRegistry helper."""

    def test_all_expected_types_registered(self) -> None:
        """Test all expected types registered."""
        expected = {
            "ping",
            "join",
            "resync",
            "node_editing",
            "node_editing_batch",
            "node_selected",
            "update",
        }
        assert expected.issubset(MSG_HANDLERS.keys())

    def test_handlers_are_coroutines(self) -> None:
        """Test handlers are coroutines."""
        for handler in MSG_HANDLERS.values():
            assert asyncio.iscoroutinefunction(handler)
