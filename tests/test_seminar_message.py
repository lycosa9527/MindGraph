"""REST seminar lines, the 30-day Redis clock, and a socket that does not save rows."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from routers.api.mindmate_seminar_ws import SEMINAR_SOCKET_INGRESS
from services.features.mindmate_seminar.config import MINDMATE_COLLAB_MAX_LIVE_SECONDS
from services.features.mindmate_seminar.manager import MindmateSeminarManager
from services.features.mindmate_seminar.message_history import PersistedCollabMessage
from services.features.mindmate_seminar.seminar_message import (
    ensure_live_seminar_room,
    send_seminar_message,
)


def _session(**overrides: object) -> MagicMock:
    session = MagicMock()
    session.id = "sess-1"
    session.code = "ABC-DEF"
    session.ended_at = None
    session.started_at = datetime(2026, 10, 1, tzinfo=UTC)
    session.expires_at = datetime(2026, 10, 1, 10, tzinfo=UTC)
    session.organization_id = None
    session.owner_user_id = 7
    session.title = "Seminar"
    session.visibility = "organization"
    session.dify_conversation_id = None
    for key, value in overrides.items():
        setattr(session, key, value)
    return session


def _manager(session: MagicMock) -> MagicMock:
    manager = MagicMock()
    manager.load_session_by_id = AsyncMock(return_value=session)
    manager.user_may_connect = AsyncMock(return_value=True)
    manager.session_is_closing = AsyncMock(return_value=False)
    manager.session_accepts_chat = AsyncMock(return_value=True)
    manager.refresh_participant_ttl = AsyncMock()
    manager.touch_activity = AsyncMock()
    manager.persist_message = AsyncMock(return_value=PersistedCollabMessage(8, 7, "2026-10-01T00:00:00+00:00"))
    manager.publish_live_room = AsyncMock(return_value=True)
    return manager


@pytest.mark.asyncio
async def test_send_seminar_message_saves_and_broadcasts_without_a_socket() -> None:
    """A chat line is stored and pushed even when the sender holds no socket."""
    session = _session()
    manager = _manager(session)
    with (
        patch(
            "services.features.mindmate_seminar.seminar_message.get_mindmate_seminar_manager",
            return_value=manager,
        ),
        patch(
            "services.features.mindmate_seminar.seminar_message.user_observes_seminar",
            AsyncMock(return_value=False),
        ),
        patch(
            "services.features.mindmate_seminar.seminar_message.ensure_live_seminar_room",
            AsyncMock(return_value=True),
        ),
        patch(
            "services.features.mindmate_seminar.seminar_message.broadcast_to_all",
            AsyncMock(),
        ) as broadcast,
    ):
        outcome = await send_seminar_message(
            session_id="sess-1",
            user_id=4,
            username="Ada",
            content="hello",
            to_mindmate=False,
            kind="chat",
        )
    assert outcome.error is None
    assert outcome.saved is not None
    assert outcome.saved.id == 8
    manager.persist_message.assert_awaited_once()
    call = broadcast.await_args
    assert call is not None
    frame = call.args[1]
    assert frame["type"] == "user_message"
    assert frame["content"] == "hello"


@pytest.mark.asyncio
async def test_send_seminar_message_rejects_observer_and_expired_room() -> None:
    """Observers and a row past 30 days do not insert a line."""
    session = _session()
    manager = _manager(session)
    with (
        patch(
            "services.features.mindmate_seminar.seminar_message.get_mindmate_seminar_manager",
            return_value=manager,
        ),
        patch(
            "services.features.mindmate_seminar.seminar_message.user_observes_seminar",
            AsyncMock(return_value=True),
        ),
    ):
        observed = await send_seminar_message(
            session_id="sess-1",
            user_id=4,
            username="Ada",
            content="hello",
            to_mindmate=False,
            kind="chat",
        )
    assert observed.error == "observer_readonly"
    manager.persist_message.assert_not_awaited()

    expired = _session(started_at=datetime.now(tz=UTC) - timedelta(seconds=MINDMATE_COLLAB_MAX_LIVE_SECONDS))
    expired_manager = _manager(expired)
    with (
        patch(
            "services.features.mindmate_seminar.seminar_message.get_mindmate_seminar_manager",
            return_value=expired_manager,
        ),
        patch(
            "services.features.mindmate_seminar.seminar_message.user_observes_seminar",
            AsyncMock(return_value=False),
        ),
    ):
        closed = await send_seminar_message(
            session_id="sess-1",
            user_id=4,
            username="Ada",
            content="hello",
            to_mindmate=False,
            kind="chat",
        )
    assert closed.error == "room_closed"
    expired_manager.persist_message.assert_not_awaited()


def test_socket_ingress_does_not_save_chat_or_minutes() -> None:
    """chat and seminar_minutes frames are not a second writer."""
    assert "chat" not in SEMINAR_SOCKET_INGRESS
    assert "seminar_minutes" not in SEMINAR_SOCKET_INGRESS
    assert SEMINAR_SOCKET_INGRESS == frozenset({"ping", "socket_ping", "read"})


@pytest.mark.asyncio
async def test_ensure_live_seminar_room_republishes_when_redis_hash_is_missing() -> None:
    """A live Postgres row rebuilds Redis after the room hash has expired."""
    session = _session(dify_conversation_id="conv-9")
    redis = AsyncMock()
    redis.hexists = AsyncMock(return_value=False)
    owner = MagicMock()
    owner.name = "Ada"
    owner.phone = None
    owner.email = None
    fake_db = AsyncMock()
    fake_result = MagicMock()
    fake_result.scalar_one_or_none.return_value = owner
    fake_db.execute = AsyncMock(return_value=fake_result)
    ctx = AsyncMock()
    ctx.__aenter__.return_value = fake_db
    ctx.__aexit__.return_value = None
    manager = _manager(session)
    with (
        patch(
            "services.features.mindmate_seminar.seminar_message.get_async_redis",
            return_value=redis,
        ),
        patch(
            "services.features.mindmate_seminar.seminar_message.system_rls_session",
            return_value=ctx,
        ),
        patch(
            "services.features.mindmate_seminar.seminar_message.bound_org_ids_for_user",
            AsyncMock(return_value=[3]),
        ),
        patch(
            "services.features.mindmate_seminar.seminar_message.get_mindmate_seminar_manager",
            return_value=manager,
        ),
    ):
        ok = await ensure_live_seminar_room(session)
    assert ok is True
    manager.publish_live_room.assert_awaited_once()
    kwargs = manager.publish_live_room.await_args.kwargs
    assert kwargs["session_id"] == "sess-1"
    assert kwargs["expires_at"] == session.expires_at
    assert kwargs["dify_conversation_id"] == "conv-9"
    assert kwargs["started_at"] == session.started_at


@pytest.mark.asyncio
async def test_redis_room_ttl_ignores_the_duration_preset() -> None:
    """A 10-hour preset does not shorten the Redis room keys below 30 days."""
    manager = MindmateSeminarManager()
    pipe = MagicMock()
    pipe.execute = AsyncMock(return_value=[])
    redis = MagicMock()
    redis.delete = AsyncMock()
    redis.pipeline.return_value = pipe
    started = datetime(2026, 10, 1, tzinfo=UTC)
    expires_at = started + timedelta(hours=10)
    with patch(
        "services.features.mindmate_seminar.manager.get_async_redis",
        return_value=redis,
    ):
        ok = await manager.publish_live_room(
            code="ABC-DEF",
            session_id="sess-1",
            owner_id=7,
            owner_name="Ada",
            org_id=3,
            title="Seminar",
            visibility="organization",
            expires_at=expires_at,
            dify_conversation_id="conv-9",
            started_at=started,
        )
    assert ok is True
    mapping = pipe.hset.call_args.kwargs["mapping"]
    assert mapping["dify_conversation_id"] == "conv-9"
    assert mapping["started_at"] == str(int(started.timestamp()))
    ttl_values = [call.args[1] for call in pipe.expire.call_args_list]
    assert ttl_values
    assert set(ttl_values) == {MINDMATE_COLLAB_MAX_LIVE_SECONDS}
