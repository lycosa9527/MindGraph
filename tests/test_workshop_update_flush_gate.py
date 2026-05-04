"""Tests that DB flush runs only after a successful live-spec merge."""

from __future__ import annotations

import unittest.mock as mock

import pytest


@pytest.mark.asyncio
async def test_schedule_flush_not_called_when_merge_returns_none() -> None:
    from routers.api import workshop_ws_handlers_update as hu

    mock_flush = mock.AsyncMock()
    mock_merge = mock.AsyncMock(return_value=None)

    class _User:
        id = 42

    class _Ctx:
        code = "room-code"
        diagram_id = "d1"
        user = _User()
        handle = None
        websocket = object()

    ctx = _Ctx()
    msg = {
        "type": "update",
        "diagram_id": "d1",
        "spec": {"v": 1, "nodes": [], "connections": []},
    }

    with mock.patch.object(hu, "schedule_live_spec_db_flush", mock_flush), mock.patch.object(
        hu, "mutate_live_spec_after_ws_update", mock_merge,
    ), mock.patch.object(hu, "get_async_redis", return_value=object()), mock.patch.object(
        hu, "is_ws_fanout_enabled", return_value=False,
    ), mock.patch.object(
        hu, "get_online_collab_manager",
    ) as mock_mgr, mock.patch.object(hu, "_send", new_callable=mock.AsyncMock), mock.patch.object(
        hu, "broadcast_to_others", new_callable=mock.AsyncMock,
    ), mock.patch.object(
        hu, "topk_record_room_activity", new_callable=mock.AsyncMock,
    ), mock.patch.object(
        hu, "topk_record_user_activity", new_callable=mock.AsyncMock,
    ):
        mock_mgr.return_value.refresh_participant_ttl = mock.AsyncMock()

        await hu.handle_update(ctx, msg)

    mock_flush.assert_not_called()
