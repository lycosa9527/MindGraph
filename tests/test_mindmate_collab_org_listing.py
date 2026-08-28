"""Org seminar listing: RLS org bind + Redis fill-in for colleagues."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.features.mindmate_collab.org_listing import (
    list_org_sessions_redis,
    list_org_sessions_sql,
    list_visible_org_sessions,
    merge_org_session_rows,
    resolve_viewer_org_id,
)


def _async_session_context(db: AsyncMock) -> AsyncMock:
    """Build an async context manager that yields *db*."""
    context = AsyncMock()

    async def _enter(*_a: object, **_k: object) -> AsyncMock:
        return db

    context.__aenter__.side_effect = _enter
    context.__aexit__.return_value = None
    return context


def test_merge_keeps_redis_peer_when_sql_only_has_own_room() -> None:
    """User 5 SQL row + user 3 Redis row both appear in the school group list."""
    merged = merge_org_session_rows(
        [{"code": "GJR-42J", "owner_user_id": 5, "title": "mine"}],
        [{"code": "8KZ-BAW", "owner_user_id": 3, "title": "peer"}],
    )
    codes = sorted(str(row["code"]) for row in merged)
    assert codes == ["8KZ-BAW", "GJR-42J"]


def test_merge_sql_wins_on_same_code() -> None:
    """SQL owner name replaces the Redis copy of the same room."""
    merged = merge_org_session_rows(
        [{"code": "8KZ-BAW", "owner_name": "王寸尺", "owner_user_id": 3}],
        [{"code": "8KZ-BAW", "owner_name": "cached", "owner_user_id": 3}],
    )
    assert len(merged) == 1
    assert merged[0]["owner_name"] == "王寸尺"


@pytest.mark.asyncio
async def test_resolve_viewer_org_id_uses_caller_value() -> None:
    """Authenticated request org id skips a probe that lacks app.organization_id."""
    with patch(
        "services.features.mindmate_collab.org_listing.user_rls_session",
    ) as session_factory:
        org_id = await resolve_viewer_org_id(5, 10)
    assert org_id == 10
    session_factory.assert_not_called()


@pytest.mark.asyncio
async def test_resolve_viewer_org_id_empty_without_org() -> None:
    """Teachers without an organization see no org seminar list."""
    viewer = MagicMock()
    viewer.organization_id = None
    probe_result = MagicMock()
    probe_result.scalar_one_or_none.return_value = viewer
    probe_db = AsyncMock()
    probe_db.execute = AsyncMock(return_value=probe_result)

    with patch(
        "services.features.mindmate_collab.org_listing.user_rls_session",
        return_value=_async_session_context(probe_db),
    ) as session_factory:
        org_id = await resolve_viewer_org_id(3, None)

    assert org_id is None
    session_factory.assert_called_once_with(3)


@pytest.mark.asyncio
async def test_sql_listing_binds_organization_id_on_rls_session() -> None:
    """SQL browse must set app.organization_id so RLS can show colleagues' rooms."""
    session_row = MagicMock()
    session_row.id = "sess-peer"
    session_row.code = "8KZ-BAW"
    session_row.title = "Seminar"
    session_row.owner_user_id = 3
    session_row.expires_at = None
    session_row.visibility = "organization"
    list_result = MagicMock()
    list_result.all.return_value = [(session_row, "王寸尺", None, None)]
    list_db = AsyncMock()
    list_db.execute = AsyncMock(return_value=list_result)

    with patch(
        "services.features.mindmate_collab.org_listing.user_rls_session",
        return_value=_async_session_context(list_db),
    ) as session_factory:
        rows = await list_org_sessions_sql(5, 10)

    session_factory.assert_called_once_with(5, organization_id=10)
    assert len(rows) == 1
    assert rows[0]["code"] == "8KZ-BAW"
    assert rows[0]["owner_name"] == "王寸尺"
    assert rows[0]["owner_user_id"] == 3


@pytest.mark.asyncio
async def test_redis_listing_includes_host_only_zero_participant_room() -> None:
    """A just-opened room stays in the group modal even if the host WS dropped."""
    redis = AsyncMock()
    pipe = MagicMock()
    pipe.smembers = MagicMock(return_value=pipe)
    pipe.hgetall = MagicMock(return_value=pipe)
    pipe.execute = AsyncMock(
        side_effect=[
            [{"8KZ-BAW"}, set()],
            [
                {
                    "session_id": "sess-3",
                    "owner_id": "3",
                    "owner_name": "王寸尺",
                    "title": "Seminar",
                    "visibility": "organization",
                    "expires_at": "9999999999",
                },
            ],
        ],
    )
    redis.pipeline = MagicMock(return_value=pipe)

    with patch(
        "services.features.mindmate_collab.org_listing.get_async_redis",
        return_value=redis,
    ):
        rows = await list_org_sessions_redis(10)

    assert len(rows) == 1
    assert rows[0]["code"] == "8KZ-BAW"
    assert rows[0]["owner_user_id"] == 3


@pytest.mark.asyncio
async def test_visible_listing_merges_sql_own_and_redis_peer() -> None:
    """End-to-end: user 5 still sees user 3's room when SQL RLS hides it."""
    sql_own = [
        {
            "session_id": "sess-5",
            "code": "GJR-42J",
            "title": "mine",
            "owner_name": "赵国庆",
            "owner_user_id": 5,
            "participant_count": 0,
            "visibility": "organization",
        },
    ]
    redis_peer = [
        {
            "session_id": "sess-3",
            "code": "8KZ-BAW",
            "title": "peer",
            "owner_name": "王寸尺",
            "owner_user_id": 3,
            "participant_count": 0,
            "visibility": "organization",
        },
    ]

    async def _counts(codes: list[str]) -> dict[str, int]:
        return {code.strip().upper(): 1 for code in codes}

    with (
        patch(
            "services.features.mindmate_collab.org_listing.resolve_viewer_org_id",
            AsyncMock(return_value=10),
        ),
        patch(
            "services.features.mindmate_collab.org_listing.list_org_sessions_sql",
            AsyncMock(return_value=sql_own),
        ),
        patch(
            "services.features.mindmate_collab.org_listing.list_org_sessions_redis",
            AsyncMock(return_value=redis_peer),
        ),
    ):
        rows = await list_visible_org_sessions(
            5,
            organization_id=10,
            participant_counts_fn=_counts,
        )

    owners = {row["owner_user_id"] for row in rows}
    assert owners == {3, 5}
    assert all(row["participant_count"] == 1 for row in rows)
