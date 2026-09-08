"""HTTP handlers for org training follow."""

from __future__ import annotations

import time
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from models.domain.auth import User

from routers.api.training_routes import (
    create_session,
    get_command,
    navigate_session,
    session_heartbeat,
    session_roster,
)
from services.features.training.payloads import NavigateBody, StartSessionBody
from services.features.training.session_store import TrainingSessionError
from services.infrastructure.http.feature_gate import feature_flag_gate


def _user(role: str, *, user_id: int = 1, org_id: int | None = 10) -> User:
    return cast(User, SimpleNamespace(id=user_id, role=role, organization_id=org_id, name=role))


def _rls_context(db: AsyncMock) -> AsyncMock:
    context = AsyncMock()
    context.__aenter__ = AsyncMock(return_value=db)
    context.__aexit__ = AsyncMock(return_value=None)
    return context


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


def _live_session() -> dict:
    return {
        "session_id": "sess-1",
        "org_id": 10,
        "instructor_id": 1,
        "instructor_name": "Ada",
        "state": "live",
        "seq": 4,
        "diagram_type": "double_bubble_map",
        "topic_options": [{"id": "opt-1", "label": "ice vs water"}],
        "started_at": 1.0,
        "expires_at": time.time() + 3600,
        "instructor_seen_at": time.time(),
    }


@pytest.mark.asyncio
async def test_feature_gate_blocks_training_when_off() -> None:
    """FEATURE_TRAINING default off hides the API."""
    call_next = AsyncMock(return_value=MagicMock(status_code=200))
    with patch(
        "services.infrastructure.http.feature_gate.config",
        SimpleNamespace(FEATURE_TRAINING=False),
    ):
        response = await feature_flag_gate(_request("/api/training/command"), call_next)
    assert response.status_code == 404
    call_next.assert_not_awaited()


@pytest.mark.asyncio
async def test_teacher_cannot_start_session() -> None:
    """Teachers receive 403 on start."""
    body = StartSessionBody(org_id=10, confirm_teacher_total=5)
    with pytest.raises(HTTPException) as exc:
        await create_session(body, current_user=_user("teacher"))
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_start_requires_matching_confirm_count() -> None:
    """Stale confirm totals are rejected."""
    body = StartSessionBody(org_id=10, confirm_teacher_total=5)
    db = AsyncMock()
    with (
        patch(
            "routers.api.training_routes.can_lead_training",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "routers.api.training_routes.system_rls_session",
            return_value=_rls_context(db),
        ),
        patch(
            "routers.api.training_routes.count_org_teachers",
            new=AsyncMock(return_value=9),
        ),
    ):
        with pytest.raises(HTTPException) as exc:
            await create_session(body, current_user=_user("superadmin", org_id=None))
    assert exc.value.status_code == 409
    detail = cast(dict[str, object], exc.value.detail)
    assert detail["code"] == "confirm_mismatch"
    assert detail["teacher_total"] == 9


@pytest.mark.asyncio
async def test_navigate_rejects_unknown_diagram_type() -> None:
    """Free URLs and unknown types are not accepted."""
    with pytest.raises(HTTPException) as exc:
        await navigate_session(
            "sess-1",
            NavigateBody(diagram_type="/mindmate"),
            org_id=10,
            current_user=_user("superadmin", org_id=None),
        )
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_late_join_command_matches_snapshot() -> None:
    """A teacher who opens the app later GETs the current snapshot."""
    session = _live_session()
    teacher = _user("teacher", org_id=10)
    with patch(
        "routers.api.training_routes.get_session",
        new=AsyncMock(return_value=dict(session)),
    ):
        response = await get_command(
            org_id=None,
            current_user=teacher,
            if_none_match=None,
        )
    assert response.headers["ETag"] == '"sess-1:4:live"'
    payload = bytes(response.body).decode("utf-8")
    assert "double_bubble_map" in payload
    assert '"seq":4' in payload
    assert '"state":"live"' in payload


@pytest.mark.asyncio
async def test_command_etag_304() -> None:
    """Unchanged snapshots return 304."""
    session = _live_session()
    teacher = _user("teacher", org_id=10)
    with patch(
        "routers.api.training_routes.get_session",
        new=AsyncMock(return_value=dict(session)),
    ):
        response = await get_command(
            org_id=None,
            current_user=teacher,
            if_none_match='"sess-1:4:live"',
        )
    assert response.status_code == 304


@pytest.mark.asyncio
async def test_command_etag_is_per_session() -> None:
    """A new session at the same seq is not a 304 against the old ETag."""
    session = _live_session()
    session["session_id"] = "sess-2"
    session["seq"] = 4
    teacher = _user("teacher", org_id=10)
    with patch(
        "routers.api.training_routes.get_session",
        new=AsyncMock(return_value=dict(session)),
    ):
        response = await get_command(
            org_id=None,
            current_user=teacher,
            if_none_match='"sess-1:4:live"',
        )
    assert response.status_code == 200
    assert response.headers["ETag"] == '"sess-2:4:live"'


@pytest.mark.asyncio
async def test_paused_command_keeps_state() -> None:
    """Paused snapshots freeze pull; clients read state from GET."""
    session = _live_session()
    session["state"] = "paused"
    session["seq"] = 6
    teacher = _user("teacher", org_id=10)
    with patch(
        "routers.api.training_routes.get_session",
        new=AsyncMock(return_value=dict(session)),
    ):
        response = await get_command(
            org_id=None,
            current_user=teacher,
            if_none_match=None,
        )
    payload = bytes(response.body).decode("utf-8")
    assert '"state":"paused"' in payload
    assert '"seq":6' in payload


@pytest.mark.asyncio
async def test_stale_command_uses_paused_etag() -> None:
    """Vanished instructor: teachers see paused and a new ETag without a Redis write."""
    session = _live_session()
    session["instructor_seen_at"] = time.time() - 200
    teacher = _user("teacher", org_id=10)
    with (
        patch(
            "routers.api.training_routes.get_session",
            new=AsyncMock(return_value=dict(session)),
        ),
        patch(
            "services.features.training.session_store.get_async_redis",
            return_value=None,
        ),
    ):
        response = await get_command(
            org_id=None,
            current_user=teacher,
            if_none_match='"sess-1:4:live"',
        )
    assert response.status_code == 200
    assert response.headers["ETag"] == '"sess-1:4:paused"'
    payload = bytes(response.body).decode("utf-8")
    assert '"state":"paused"' in payload
    assert '"seq":4' in payload


@pytest.mark.asyncio
async def test_roster_paginates_over_200() -> None:
    """Instructor roster pages at 50 of 210."""
    rows = [{"user_id": index, "name": f"T{index}"} for index in range(210)]
    db = AsyncMock()
    execute_result = MagicMock()
    execute_result.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(return_value=execute_result)
    with (
        patch(
            "routers.api.training_routes.can_lead_training",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "routers.api.training_routes.get_session",
            new=AsyncMock(return_value=_live_session()),
        ),
        patch(
            "routers.api.training_routes.list_activity",
            new=AsyncMock(return_value=rows),
        ),
        patch(
            "routers.api.training_routes.system_rls_session",
            return_value=_rls_context(db),
        ),
    ):
        first = await session_roster(
            "sess-1",
            org_id=10,
            q="",
            limit=50,
            offset=0,
            current_user=_user("superadmin", org_id=None),
        )
        later = await session_roster(
            "sess-1",
            org_id=10,
            q="",
            limit=50,
            offset=200,
            current_user=_user("superadmin", org_id=None),
        )
    assert first["total"] == 210
    assert len(first["items"]) == 50
    assert later["items"][0]["user_id"] == 200
    assert len(later["items"]) == 10


@pytest.mark.asyncio
async def test_stale_heartbeat_returns_none_snapshot() -> None:
    """A vanished session is current truth, not a 404."""
    with (
        patch(
            "routers.api.training_routes.can_lead_training",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "routers.api.training_routes.get_session",
            new=AsyncMock(return_value=None),
        ),
    ):
        body = await session_heartbeat(
            "c54f550e-3fb6-465c-ae88-568e25deff1f",
            org_id=10,
            current_user=_user("superadmin", org_id=None),
        )
    assert body["state"] == "none"
    assert body["session_id"] is None


@pytest.mark.asyncio
async def test_stale_heartbeat_returns_replacement_session() -> None:
    """Heartbeating an old id returns the live replacement snapshot."""
    with (
        patch(
            "routers.api.training_routes.can_lead_training",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "routers.api.training_routes.get_session",
            new=AsyncMock(return_value=_live_session()),
        ),
    ):
        body = await session_heartbeat(
            "old-session",
            org_id=10,
            current_user=_user("superadmin", org_id=None),
        )
    assert body["session_id"] == "sess-1"
    assert body["state"] == "live"


@pytest.mark.asyncio
async def test_heartbeat_not_owner_returns_current_snapshot() -> None:
    """Takeover does not 403 the previous host's leftover timer."""
    session = _live_session()
    session["instructor_id"] = 9
    session["instructor_name"] = "Bea"
    with (
        patch(
            "routers.api.training_routes.can_lead_training",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "routers.api.training_routes.get_session",
            new=AsyncMock(return_value=session),
        ),
        patch(
            "routers.api.training_routes.heartbeat",
            new=AsyncMock(side_effect=TrainingSessionError("not_owner", "Only the owner")),
        ),
    ):
        body = await session_heartbeat(
            "sess-1",
            org_id=10,
            current_user=_user("superadmin", org_id=None),
        )
    assert body["instructor_id"] == 9
    assert body["session_id"] == "sess-1"
