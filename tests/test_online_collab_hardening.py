"""Focused regression tests for online collaboration hardening."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@dataclass
class _User:
    id: int = 123
    username: str = "teacher"


class _FakeWebSocket:
    """Minimal WebSocket stand-in for pre-accept rejection tests."""

    def __init__(self) -> None:
        self.headers: dict[str, str] = {"origin": "https://evil.example"}
        self.query_params: dict[str, str] = {}
        self.closed: list[dict[str, Any]] = []

    async def close(self, *, code: int, reason: str) -> None:
        self.closed.append({"code": code, "reason": reason})


class _ResumeRedis:
    def __init__(self, diagram_id: str | None) -> None:
        self.diagram_id = diagram_id

    async def get(self, _key: str) -> str | None:
        return self.diagram_id


@pytest.mark.asyncio
async def test_origin_rejected_before_join_mutates_workshop_state() -> None:
    """A bad Origin must not reach the Redis/DB join path."""
    from routers.api import workshop_ws

    websocket = _FakeWebSocket()
    resolve_join = AsyncMock()

    with (
        patch.object(
            workshop_ws,
            "authenticate_canvas_collab_user",
            AsyncMock(return_value=(_User(), None)),
        ),
        patch.object(
            workshop_ws,
            "load_collab_ws_allowed_origins_env",
            return_value=frozenset({"https://app.example"}),
        ),
        patch.object(
            workshop_ws,
            "canvas_collab_websocket_origin_is_allowed",
            return_value=False,
        ),
        patch.object(workshop_ws, "record_ws_collab_origin_reject"),
        patch.object(workshop_ws, "resolve_canvas_collab_join", resolve_join),
    ):
        await workshop_ws.canvas_collab_websocket(websocket, "ABC-234")

    resolve_join.assert_not_awaited()
    assert websocket.closed == [
        {
            "code": 1008,
            "reason": "Cross-origin collaboration is not allowed",
        }
    ]


@pytest.mark.asyncio
async def test_resume_rate_limit_bypass_requires_current_diagram_match() -> None:
    """A stale resume token for a recycled code must not skip join rate limits."""
    from routers.api import workshop_ws_auth as auth

    websocket = _FakeWebSocket()
    websocket.query_params["resume"] = "resume-token"
    user = _User(id=123)

    with (
        patch.object(
            auth,
            "peek_join_resume_claims_async",
            AsyncMock(return_value={"u": 123, "c": "ABC-123", "d": "old-diagram"}),
        ),
        patch.object(auth, "get_async_redis", return_value=_ResumeRedis("new-diagram")),
    ):
        verified = await auth._has_verified_resume_for_rate_limit(
            websocket,
            user,
            "ABC-123",
        )

    assert verified is False


class _DiagramRow:
    def __init__(self, workshop_code: str) -> None:
        self.workshop_code = workshop_code


class _ScalarResult:
    def __init__(self, value: Any) -> None:
        self._value = value

    def first(self) -> Any:
        return self._value


class _ExecuteResult:
    def __init__(self, value: Any) -> None:
        self._value = value

    def scalars(self) -> _ScalarResult:
        return _ScalarResult(self._value)


@pytest.mark.asyncio
async def test_idle_stop_flush_failure_keeps_session_intact() -> None:
    """Idle cleanup must not destroy or clear a room when DB flush fails."""
    from services.online_collab.core import online_collab_stop as stop_ops

    fake_db = AsyncMock()
    fake_db.execute = AsyncMock(return_value=_ExecuteResult(_DiagramRow("ABC-123")))
    fake_context = AsyncMock()
    fake_context.__aenter__.return_value = fake_db
    fake_context.__aexit__.return_value = None
    fake_redis = object()
    manager = MagicMock()
    manager.destroy_session = AsyncMock()

    with (
        patch.object(stop_ops, "AsyncSessionLocal", return_value=fake_context),
        patch.object(stop_ops, "get_async_redis", return_value=fake_redis),
        patch.object(
            stop_ops,
            "flush_live_spec_to_db_in_session",
            AsyncMock(return_value=False),
        ) as flush_mock,
        patch.object(
            stop_ops,
            "_extend_room_ttl_after_flush_failure",
            AsyncMock(),
        ) as extend_mock,
        patch(
            "services.online_collab.lifecycle.online_collab_session_closing"
            ".mark_workshop_session_closing",
            AsyncMock(),
        ),
        patch(
            "routers.api.workshop_ws_broadcast.broadcast_workshop_session_closing",
            AsyncMock(),
        ),
        patch.object(stop_ops.asyncio, "sleep", AsyncMock()),
        patch(
            "services.online_collab.core.online_collab_manager"
            ".get_online_collab_manager",
            return_value=manager,
        ),
    ):
        stopped = await stop_ops.stop_online_collab_for_room_idle_impl(
            diagram_id="diagram-1",
            expected_code="ABC-123",
        )

    assert stopped is False
    flush_mock.assert_awaited_once_with(fake_db, fake_redis, "ABC-123", "diagram-1")
    extend_mock.assert_awaited_once_with(fake_redis, "ABC-123")
    manager.destroy_session.assert_not_awaited()
    fake_db.rollback.assert_awaited()
    fake_db.commit.assert_not_awaited()


class _AtomicRedis:
    def __init__(self) -> None:
        self.data: dict[str, str] = {}
        self.eval_calls = 0

    async def setex(self, key: str, _ttl: int, val: str) -> bool:
        self.data[key] = val
        return True

    async def get(self, key: str) -> str | None:
        return self.data.get(key)

    async def eval(self, _script: str, _num_keys: int, key: str, *args: str) -> int:
        self.eval_calls += 1
        payload = self.data.get(key)
        if payload is None:
            return 0
        decoded = json.loads(payload)
        if (
            str(decoded.get("u")) == args[0]
            and str(decoded.get("c")) == args[1]
            and str(decoded.get("d")) == args[2]
        ):
            self.data.pop(key, None)
            await asyncio.sleep(0)
            return 1
        return 0


@pytest.mark.asyncio
async def test_resume_token_consume_is_single_use_atomic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Concurrent reconnects must not both consume the same resume token."""
    from services.online_collab.participant import workshop_join_resume_tokens as tokens

    fake = _AtomicRedis()
    monkeypatch.setattr(tokens, "get_async_redis", lambda: fake)

    raw_token = await tokens.mint_join_resume_token_async(
        user_id=101,
        workshop_code_upper="CODE-AAA",
        diagram_id="diag-uuid",
    )

    outcomes = await asyncio.gather(
        tokens.try_consume_join_resume_token_async(
            raw_query_token=raw_token,
            user_id=101,
            workshop_code_upper="CODE-AAA",
            diagram_id="diag-uuid",
        ),
        tokens.try_consume_join_resume_token_async(
            raw_query_token=raw_token,
            user_id=101,
            workshop_code_upper="CODE-AAA",
            diagram_id="diag-uuid",
        ),
    )

    assert sorted(outcomes) == [False, True]
    assert fake.eval_calls == 2
    assert not fake.data


@pytest.mark.asyncio
async def test_full_spec_update_rejects_when_foreign_node_lock_exists() -> None:
    """Full-spec replacement must not delete or overwrite another user's lock."""
    from routers.api import workshop_ws_handlers_update as update_handler

    websocket = AsyncMock()
    ctx = MagicMock()
    ctx.code = "ABC-123"
    ctx.diagram_id = "diagram-1"
    ctx.user = _User(id=10)
    ctx.handle = None
    ctx.websocket = websocket
    manager = MagicMock()
    manager.refresh_participant_ttl = AsyncMock()

    with (
        patch.object(update_handler, "_diagram_update_validation_error", return_value=None),
        patch.object(update_handler, "collab_update_schema_error", return_value=None),
        patch.object(update_handler, "workshop_session_is_closing", AsyncMock(return_value=False)),
        patch.object(update_handler, "get_online_collab_manager", return_value=manager),
        patch.object(update_handler, "get_async_redis", return_value=object()),
        patch.object(update_handler, "is_ws_fanout_enabled", return_value=False),
        patch.object(
            update_handler,
            "build_locked_by_others_node_ids",
            return_value={"locked-node"},
        ),
        patch.object(
            update_handler,
            "mutate_live_spec_after_ws_update",
            AsyncMock(),
        ) as mutate_mock,
    ):
        await update_handler.handle_update(
            ctx,
            {
                "type": "update",
                "diagram_id": "diagram-1",
                "spec": {"nodes": [], "connections": []},
            },
        )

    mutate_mock.assert_not_awaited()
    websocket.send_json.assert_awaited_once()
    payload = websocket.send_json.await_args.args[0]
    assert payload["code"] == "update_rejected"


@pytest.mark.asyncio
async def test_role_change_publishes_cross_worker_control() -> None:
    """Fanout mode must not require the target socket to be local."""
    from services.features import workshop_ws_role_change as roles
    from services.features.workshop_ws_connection_state import ConnectionHandle

    requester = ConnectionHandle(
        websocket=MagicMock(),
        code="ABC-123",
        user_id=10,
        send_queue=asyncio.Queue(),
        role="host",
    )
    ctx = MagicMock()
    ctx.code = "ABC-123"
    ctx.owner_id = 10
    ctx.user = _User(id=10)
    ctx.handle = requester

    with (
        patch.object(roles, "is_ws_fanout_enabled", return_value=True),
        patch.object(roles, "_publish_role_control", AsyncMock(return_value=True)) as publish,
        patch(
            "routers.api.workshop_ws_broadcast.broadcast_to_others",
            AsyncMock(),
        ) as broadcast,
    ):
        await roles.handle_role_change(
            ctx,
            {"type": "role_change", "user_id": 99, "to": "viewer"},
        )

    publish.assert_awaited_once()
    broadcast.assert_awaited_once()
    _kind, body = requester.send_queue.get_nowait()
    assert '"type": "role_change_ack"' in body
    assert '"user_id": 99' in body


def test_diagram_model_enforces_unique_active_workshop_code() -> None:
    from models.domain.diagrams import Diagram

    indexes = {index.name: index for index in Diagram.__table__.indexes}
    index = indexes["ix_diagrams_workshop_code_unique_active"]

    assert index.unique is True
    assert [column.name for column in index.columns] == ["workshop_code"]
    predicate = str(index.dialect_options["postgresql"]["where"])
    assert "workshop_code IS NOT NULL" in predicate
    assert "is_deleted IS false" in predicate
