"""MindMate collab manager unit tests (single-host rule)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.features.mindmate_seminar.manager import MindmateSeminarManager


@pytest.mark.asyncio
async def test_stop_hosted_sessions_for_user_stops_each_active_row() -> None:
    """Hosted-session cleanup invokes stop_session for every active owned row."""
    mgr = MindmateSeminarManager()
    row_a = MagicMock(id="sess-a")
    row_b = MagicMock(id="sess-b")

    fake_sess = AsyncMock()
    fake_result = MagicMock()
    fake_result.scalars.return_value.all.return_value = [row_a, row_b]
    fake_sess.execute = AsyncMock(return_value=fake_result)

    context = AsyncMock()

    async def _enter(*_a, **_k):
        return fake_sess

    context.__aenter__.side_effect = _enter
    context.__aexit__.return_value = None

    stop_mock = AsyncMock(return_value=True)

    with (
        patch(
            "services.features.mindmate_seminar.manager.user_rls_session",
            return_value=context,
        ),
        patch.object(mgr, "stop_session", stop_mock),
    ):
        count = await mgr.stop_hosted_sessions_for_user(42)

    assert count == 2
    assert stop_mock.await_count == 2
    stop_mock.assert_any_await("sess-a", 42, reason="single_host")
    stop_mock.assert_any_await("sess-b", 42, reason="single_host")


@pytest.mark.asyncio
async def test_session_payload_includes_owner_and_expiry() -> None:
    """Hosted session lookup exposes owner, participant count, and expiry."""
    mgr = MindmateSeminarManager()
    session = MagicMock()
    session.id = "uuid-1"
    session.code = "ABC-DEF"
    session.title = "Room"
    session.visibility = "organization"
    session.owner_user_id = 7
    session.organization_id = 3
    session.expires_at = datetime(2026, 7, 3, 12, 0, tzinfo=UTC)

    fake_sess = AsyncMock()
    fake_result = MagicMock()
    fake_result.scalar_one_or_none.return_value = session
    fake_sess.execute = AsyncMock(return_value=fake_result)
    context = AsyncMock()

    async def _enter(*_a, **_k):
        return fake_sess

    context.__aenter__.side_effect = _enter
    context.__aexit__.return_value = None

    with (
        patch(
            "services.features.mindmate_seminar.manager.user_rls_session",
            return_value=context,
        ),
        patch.object(mgr, "participant_count", AsyncMock(return_value=4)),
    ):
        payload = await mgr.get_hosted_session(7)

    assert payload is not None
    assert payload["owner_user_id"] == 7
    assert payload["participant_count"] == 4
    assert payload["expires_at"].startswith("2026-07-03")


@pytest.mark.asyncio
async def test_stop_session_owner_already_ended_is_success() -> None:
    """A second host stop after ended_at is set must not look like a failure."""
    mgr = MindmateSeminarManager()
    session = MagicMock()
    session.ended_at = datetime(2026, 8, 28, 6, 12, 27, tzinfo=UTC)
    session.owner_user_id = 3

    fake_sess = AsyncMock()
    fake_result = MagicMock()
    fake_result.scalar_one_or_none.return_value = session
    fake_sess.execute = AsyncMock(return_value=fake_result)
    context = AsyncMock()
    context.__aenter__.return_value = fake_sess
    context.__aexit__.return_value = None

    with patch(
        "services.features.mindmate_seminar.manager.system_rls_session",
        return_value=context,
    ):
        ok = await mgr.stop_session("sess-ended", 3, reason="owner")

    assert ok is True


@pytest.mark.asyncio
async def test_stop_session_owner_hidden_ended_row_is_success() -> None:
    """RLS may hide an ended row; host retry still settles as success via system read."""
    mgr = MindmateSeminarManager()
    ended = MagicMock()
    ended.ended_at = datetime(2026, 8, 28, 6, 12, 27, tzinfo=UTC)
    ended.owner_user_id = 3

    user_sess = AsyncMock()
    user_result = MagicMock()
    user_result.scalar_one_or_none.return_value = None
    user_sess.execute = AsyncMock(return_value=user_result)
    user_ctx = AsyncMock()
    user_ctx.__aenter__.return_value = user_sess
    user_ctx.__aexit__.return_value = None

    system_sess = AsyncMock()
    system_result = MagicMock()
    system_result.scalar_one_or_none.return_value = ended
    system_sess.execute = AsyncMock(return_value=system_result)
    system_ctx = AsyncMock()
    system_ctx.__aenter__.return_value = system_sess
    system_ctx.__aexit__.return_value = None

    with (
        patch(
            "services.features.mindmate_seminar.manager.user_rls_session",
            return_value=user_ctx,
        ),
        patch(
            "services.features.mindmate_seminar.manager.system_rls_session",
            return_value=system_ctx,
        ),
    ):
        ok = await mgr.stop_session("sess-ended", 3, reason="owner")

    assert ok is True


@pytest.mark.asyncio
async def test_stop_session_non_owner_already_ended_is_rejected() -> None:
    """Ended rooms stay unauthorized for anyone other than the host."""
    mgr = MindmateSeminarManager()
    session = MagicMock()
    session.ended_at = datetime(2026, 8, 28, 6, 12, 27, tzinfo=UTC)
    session.owner_user_id = 3

    fake_sess = AsyncMock()
    fake_result = MagicMock()
    fake_result.scalar_one_or_none.return_value = session
    fake_sess.execute = AsyncMock(return_value=fake_result)
    context = AsyncMock()
    context.__aenter__.return_value = fake_sess
    context.__aexit__.return_value = None

    with (
        patch(
            "services.features.mindmate_seminar.manager.system_rls_session",
            return_value=context,
        ),
        patch(
            "services.features.mindmate_seminar.manager.actor_is_seminar_leader",
            AsyncMock(return_value=False),
        ),
    ):
        ok = await mgr.stop_session("sess-ended", 5, reason="owner")

    assert ok is False


@pytest.mark.asyncio
async def test_join_by_code_rejected_when_room_closing() -> None:
    """REST join fails while the closing marker is set."""
    mgr = MindmateSeminarManager()
    session = MagicMock()
    session.code = "ABC-DEF"
    session.visibility = "organization"
    session.expires_at = None
    session.owner_user_id = 1
    session.organization_id = 10

    with (
        patch.object(mgr, "load_session_by_code", AsyncMock(return_value=session)),
        patch.object(mgr, "session_is_closing", AsyncMock(return_value=True)),
    ):
        payload, error = await mgr.join_by_code(2, "ABC-DEF")

    assert payload is None
    assert error == "still_live"


@pytest.mark.asyncio
async def test_join_by_code_returns_payload_after_permission_check() -> None:
    """REST join validates permissions and returns session payload without WS registration."""
    mgr = MindmateSeminarManager()
    session = MagicMock()
    session.code = "ABC-DEF"
    session.visibility = "organization"
    session.expires_at = None
    session.owner_user_id = 1
    session.organization_id = 10

    validate_mock = AsyncMock(return_value=True)
    payload_mock = AsyncMock(return_value={"code": "ABC-DEF", "participant_count": 2})

    with (
        patch.object(mgr, "load_session_by_code", AsyncMock(return_value=session)),
        patch.object(mgr, "session_is_closing", AsyncMock(return_value=False)),
        patch.object(mgr, "_validate_join_permissions", validate_mock),
        patch.object(mgr, "_session_payload", payload_mock),
    ):
        payload, error = await mgr.join_by_code(2, "ABC-DEF")

    validate_mock.assert_awaited_once_with(session, 2)
    assert error is None
    assert payload == {"code": "ABC-DEF", "participant_count": 2}


@pytest.mark.asyncio
async def test_join_by_code_allows_accepted_member_from_another_school() -> None:
    """A phone invite that was accepted is enough. Same-school is not checked again."""
    mgr = MindmateSeminarManager()
    session = MagicMock()
    session.id = "sess-org"
    session.code = "ABC-DEF"
    session.visibility = "organization"
    session.owner_user_id = 1
    session.organization_id = 4

    may_join = AsyncMock(return_value=False)
    with (
        patch.object(mgr, "load_session_by_code", AsyncMock(return_value=session)),
        patch.object(mgr, "session_is_closing", AsyncMock(return_value=False)),
        patch(
            "services.features.mindmate_seminar.manager.seminar_room_is_closed",
            AsyncMock(return_value=True),
        ),
        patch(
            "services.features.mindmate_seminar.manager.list_invited_member_ids",
            AsyncMock(return_value=[99]),
        ),
        patch(
            "services.features.mindmate_seminar.manager.accepted_member_ids",
            AsyncMock(return_value=[99]),
        ),
        patch(
            "services.features.mindmate_seminar.manager.user_may_join_mindmate_seminar",
            may_join,
        ),
        patch.object(mgr, "_session_payload", AsyncMock(return_value={"code": "ABC-DEF"})),
    ):
        payload, error = await mgr.join_by_code(99, "ABC-DEF")

    assert error is None
    assert payload == {"code": "ABC-DEF"}
    may_join.assert_not_awaited()


@pytest.mark.asyncio
async def test_join_by_code_rejects_pending_invite_from_another_school() -> None:
    """A cross-school invite stays closed until that teacher agrees."""
    mgr = MindmateSeminarManager()
    session = MagicMock()
    session.id = "sess-org"
    session.code = "ABC-DEF"
    session.visibility = "organization"
    session.owner_user_id = 1
    session.organization_id = 4

    with (
        patch.object(mgr, "load_session_by_code", AsyncMock(return_value=session)),
        patch.object(mgr, "session_is_closing", AsyncMock(return_value=False)),
        patch(
            "services.features.mindmate_seminar.manager.seminar_room_is_closed",
            AsyncMock(return_value=True),
        ),
        patch(
            "services.features.mindmate_seminar.manager.list_invited_member_ids",
            AsyncMock(return_value=[99]),
        ),
        patch(
            "services.features.mindmate_seminar.manager.accepted_member_ids",
            AsyncMock(return_value=[]),
        ),
    ):
        payload, error = await mgr.join_by_code(99, "ABC-DEF")

    assert payload is None
    assert error == "forbidden"


@pytest.mark.asyncio
async def test_join_by_code_rejected_when_not_allowed() -> None:
    """REST join fails when the user may not join the room."""
    mgr = MindmateSeminarManager()
    session = MagicMock()
    session.code = "ABC-DEF"
    session.visibility = "network"
    session.expires_at = None
    session.owner_user_id = 1
    session.organization_id = 10

    with (
        patch.object(mgr, "load_session_by_code", AsyncMock(return_value=session)),
        patch.object(mgr, "session_is_closing", AsyncMock(return_value=False)),
        patch.object(mgr, "_validate_join_permissions", AsyncMock(return_value=False)),
    ):
        payload, error = await mgr.join_by_code(2, "ABC-DEF")

    assert payload is None
    assert error == "forbidden"


@pytest.mark.asyncio
async def test_resolve_dify_conversation_id_prefers_redis_meta() -> None:
    """WS chat uses the latest Dify conversation id from Redis session meta."""
    mgr = MindmateSeminarManager()
    with patch.object(
        mgr,
        "get_session_meta",
        AsyncMock(return_value={"dify_conversation_id": "conv-redis"}),
    ):
        conv_id = await mgr.resolve_dify_conversation_id("ABC-DEF", fallback="conv-stale")

    assert conv_id == "conv-redis"


@pytest.mark.asyncio
async def test_list_org_sessions_passes_caller_org_and_counts() -> None:
    """Route org id is forwarded so listing does not open a bare user RLS session."""
    mgr = MindmateSeminarManager()
    listed = [{"code": "8KZ-BAW", "owner_user_id": 3}]
    with patch(
        "services.features.mindmate_seminar.manager.list_visible_org_sessions",
        AsyncMock(return_value=listed),
    ) as listing:
        sessions = await mgr.list_org_sessions(5, organization_id=10)

    listing.assert_awaited_once_with(
        5,
        organization_id=10,
        participant_counts_fn=mgr.participant_counts_for_codes,
    )
    assert sessions == listed


@pytest.mark.asyncio
async def test_participant_counts_for_codes_batches_hlen() -> None:
    """Org browse uses one Redis pipeline for many participant counts."""
    mgr = MindmateSeminarManager()
    redis = AsyncMock()
    pipe = AsyncMock()
    pipe.hlen = MagicMock(return_value=pipe)
    pipe.execute = AsyncMock(return_value=[3, 5])
    redis.pipeline = MagicMock(return_value=pipe)

    with patch(
        "services.features.mindmate_seminar.manager.get_async_redis",
        return_value=redis,
    ):
        counts = await mgr.participant_counts_for_codes(["ABC-DEF", "GHI-JKL"])

    assert counts == {"ABC-DEF": 3, "GHI-JKL": 5}
    assert pipe.hlen.call_count == 2
