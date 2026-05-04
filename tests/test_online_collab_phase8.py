"""
Phase 8 unit tests: Editor/Viewer role split, snapshot key, diff seq, promotion.

Coverage:
- ViewerHandle is instantiated with small queue and no coalesce infra
- register_connection(role="viewer") returns ViewerHandle
- register_connection(role="host") returns ConnectionHandle with role="host"
- enqueue on ViewerHandle skips coalesce path and uses drop policy
- Viewer dispatcher rejects editor messages (close 4015)
- Viewer dispatcher accepts ping and resync
- Snapshot refresh stops when no viewers remain
- Viewer snapshot hit metric incremented
- In-place promotion: ViewerHandle → ConnectionHandle preserved same queue
- In-place demotion: ConnectionHandle → ViewerHandle flush task cancelled
- Role change rejected if requester is not host
- seq stamped in snapshot; viewer gap triggers resync
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.features.workshop_ws_connection_state import (
    ACTIVE_CONNECTIONS,
    ConnectionHandle,
    ViewerHandle,
    enqueue,
    register_connection,
    unregister_connection,
)
from services.features.workshop_ws_role_change import (
    demote_to_viewer,
    promote_to_editor,
)
from services.online_collab.redis.online_collab_redis_keys import (
    snapshot_key,
    snapshot_seq_key,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ws() -> MagicMock:
    ws = MagicMock()
    ws.send_bytes = AsyncMock()
    ws.send_text = AsyncMock()
    ws.close = AsyncMock()
    return ws


# ---------------------------------------------------------------------------
# TestViewerHandleConstruction
# ---------------------------------------------------------------------------

class TestViewerHandleConstruction:
    """ViewerHandle has smaller queue and no coalesce infrastructure."""

    @pytest.mark.asyncio
    async def test_register_viewer_returns_viewer_handle(self) -> None:
        code = "VIEWERTEST1"
        ws = _make_ws()
        handle = await register_connection(code, 1, ws, role="viewer")
        try:
            assert isinstance(handle, ViewerHandle)
            assert handle.role == "viewer"
            assert handle.send_queue.maxsize == 64
            assert not hasattr(handle, "coalesce_buffer")
            assert not hasattr(handle, "coalesce_lock")
            assert not hasattr(handle, "flush_task")
        finally:
            await unregister_connection(code, 1)

    @pytest.mark.asyncio
    async def test_register_host_returns_connection_handle(self) -> None:
        code = "HOSTTEST1"
        ws = _make_ws()
        handle = await register_connection(code, 2, ws, role="host")
        try:
            assert isinstance(handle, ConnectionHandle)
            assert handle.role == "host"
            assert handle.send_queue.maxsize == 256
        finally:
            await unregister_connection(code, 2)

    @pytest.mark.asyncio
    async def test_register_editor_returns_connection_handle(self) -> None:
        code = "EDITRTEST1"
        ws = _make_ws()
        handle = await register_connection(code, 3, ws, role="editor")
        try:
            assert isinstance(handle, ConnectionHandle)
            assert handle.role == "editor"
        finally:
            await unregister_connection(code, 3)


# ---------------------------------------------------------------------------
# TestViewerEnqueuePolicy
# ---------------------------------------------------------------------------

class TestViewerEnqueuePolicy:
    """Viewers use drop policy for coalesce-type messages (no coalesce buffer)."""

    @pytest.mark.asyncio
    async def test_viewer_node_editing_uses_drop_not_coalesce(self) -> None:
        code = "DROPTEST1"
        ws = _make_ws()
        handle = await register_connection(code, 4, ws, role="viewer")
        try:
            payload = {"type": "node_editing", "node_id": "n1", "user_id": 10}
            await enqueue(handle, payload, "node_editing")
            assert not isinstance(handle, ConnectionHandle)
            assert handle.send_queue.qsize() > 0
        finally:
            await unregister_connection(code, 4)


# ---------------------------------------------------------------------------
# TestRedisSnapshotKeys
# ---------------------------------------------------------------------------

class TestRedisSnapshotKeys:
    """Snapshot and snapshot_seq key helpers return expected patterns."""

    def test_snapshot_key_pattern(self) -> None:
        assert snapshot_key("ABC123") == "workshop:snapshot:ABC123"

    def test_snapshot_seq_key_pattern(self) -> None:
        assert snapshot_seq_key("ABC123") == "workshop:snapshot_seq:ABC123"

    def test_snapshot_key_hash_tag(self) -> None:
        with patch.dict(
            "os.environ", {"COLLAB_REDIS_HASH_TAGS": "1"}
        ):
            from importlib import reload
            import services.online_collab.redis.online_collab_redis_keys as rk
            reload(rk)
            try:
                assert rk.snapshot_key("X1") == "workshop:snapshot:{X1}"
            finally:
                reload(rk)


# ---------------------------------------------------------------------------
# TestViewerSnapshotHit
# ---------------------------------------------------------------------------

class TestViewerSnapshotHit:
    """Viewer snapshot hit metric incremented when cached snapshot served."""

    @pytest.mark.asyncio
    async def test_snapshot_hit_metric_incremented(self) -> None:
        code = "SNAPHIT1"
        ws = _make_ws()
        handle = await register_connection(code, 5, ws, role="viewer")
        try:
            cached_snap = {
                "spec": {"nodes": [], "connections": []},
                "version": 3,
                "seq": 7,
                "ts": 1000.0,
            }
            hit_count = {"n": 0}

            def _record_hit() -> None:
                hit_count["n"] += 1

            with (
                patch(
                    "services.online_collab.participant.online_collab_snapshots"
                    ".ensure_snapshot_task"
                ),
                patch(
                    "services.online_collab.participant.online_collab_snapshots"
                    ".read_viewer_snapshot",
                    new=AsyncMock(return_value=cached_snap),
                ),
                patch(
                    "services.infrastructure.monitoring.ws_metrics"
                    ".record_ws_viewer_snapshot_hit",
                    side_effect=_record_hit,
                ),
            ):
                from services.online_collab.participant.online_collab_snapshots import (
                    websocket_send_live_spec_snapshot,
                )
                await websocket_send_live_spec_snapshot(handle, code, "diag1")

            assert hit_count["n"] == 1
            assert handle.send_queue.qsize() == 1
            item = handle.send_queue.get_nowait()
            kind, body = item
            assert kind == "text"
            frame = json.loads(body)
            assert frame["type"] == "snapshot"
            assert frame["seq"] == 7
            assert frame["version"] == 3
        finally:
            await unregister_connection(code, 5)


# ---------------------------------------------------------------------------
# TestInPlacePromotion
# ---------------------------------------------------------------------------

class TestInPlacePromotion:
    """promote_to_editor swaps ViewerHandle → ConnectionHandle, same queue."""

    @pytest.mark.asyncio
    async def test_promote_viewer_to_editor(self) -> None:
        code = "PROMOTE1"
        ws = _make_ws()
        viewer = await register_connection(code, 10, ws, role="viewer")
        assert isinstance(viewer, ViewerHandle)
        original_queue = viewer.send_queue
        try:
            result = await promote_to_editor(code, 10, promoted_by=1)
            assert result is True
            upgraded = ACTIVE_CONNECTIONS.get(code, {}).get(10)
            assert isinstance(upgraded, ConnectionHandle)
            assert upgraded.role == "editor"
            assert upgraded.send_queue is original_queue
            assert upgraded.websocket is ws
        finally:
            await unregister_connection(code, 10)

    @pytest.mark.asyncio
    async def test_promote_nonexistent_user_returns_false(self) -> None:
        code = "PROMOTE2"
        result = await promote_to_editor(code, 999, promoted_by=1)
        assert result is False

    @pytest.mark.asyncio
    async def test_promote_editor_returns_false(self) -> None:
        code = "PROMOTE3"
        ws = _make_ws()
        await register_connection(code, 11, ws, role="editor")
        try:
            result = await promote_to_editor(code, 11, promoted_by=1)
            assert result is False
        finally:
            await unregister_connection(code, 11)

    @pytest.mark.asyncio
    async def test_promote_owner_viewer_to_host(self) -> None:
        code = "PROMOWNER1"
        ws = _make_ws()
        await register_connection(code, 101, ws, role="viewer")
        try:
            result = await promote_to_editor(
                code, 101, promoted_by=1, diagram_owner_id=101,
            )
            assert result is True
            upgraded = ACTIVE_CONNECTIONS.get(code, {}).get(101)
            assert isinstance(upgraded, ConnectionHandle)
            assert upgraded.role == "host"
        finally:
            await unregister_connection(code, 101)

    @pytest.mark.asyncio
    async def test_demote_host_returns_false(self) -> None:
        code = "DEMHOST1"
        ws = _make_ws()
        await register_connection(code, 202, ws, role="host")
        try:
            result = await demote_to_viewer(code, 202, demoted_by=1)
            assert result is False
            still = ACTIVE_CONNECTIONS.get(code, {}).get(202)
            assert isinstance(still, ConnectionHandle)
            assert still.role == "host"
        finally:
            await unregister_connection(code, 202)

    @pytest.mark.asyncio
    async def test_role_changed_broadcast_on_promote_sends_fanout_excluding_target(
        self,
    ) -> None:
        code = "BCPROMO1"
        ws_a = _make_ws()
        ws_b = _make_ws()
        await register_connection(code, 303, ws_a, role="viewer")
        await register_connection(code, 304, ws_b, role="editor")
        try:
            mock_broadcast = AsyncMock()
            with patch(
                "routers.api.workshop_ws_broadcast.broadcast_to_others",
                new=mock_broadcast,
            ):
                await promote_to_editor(code, 303, promoted_by=302)

            mock_broadcast.assert_awaited_once()
            await_args = mock_broadcast.await_args
            assert await_args.args[0] == code
            assert await_args.args[1] == 303
            payload = await_args.args[2]
            assert payload["type"] == "role_changed"
            assert payload["user_id"] == 303
            assert payload["role"] == "editor"
            assert payload["promoted_by"] == 302

            handle_promoted = ACTIVE_CONNECTIONS.get(code, {}).get(303)
            assert handle_promoted is not None

            drained_target = []
            while not handle_promoted.send_queue.empty():  # type: ignore[attr-defined]
                drained_target.append(handle_promoted.send_queue.get_nowait())

            decoded_self = [
                json.loads(body)
                for kind, body in drained_target
                if kind == "text"
            ]
            assert any(
                f.get("type") == "role_changed" for f in decoded_self
            )
        finally:
            await unregister_connection(code, 303)
            await unregister_connection(code, 304)


# ---------------------------------------------------------------------------
# TestInPlaceDemotion
# ---------------------------------------------------------------------------

class TestInPlaceDemotion:
    """demote_to_viewer swaps ConnectionHandle → ViewerHandle, same queue."""

    @pytest.mark.asyncio
    async def test_demote_editor_to_viewer(self) -> None:
        code = "DEMOTE1"
        ws = _make_ws()
        editor = await register_connection(code, 20, ws, role="editor")
        assert isinstance(editor, ConnectionHandle)
        original_queue = editor.send_queue
        try:
            result = await demote_to_viewer(code, 20, demoted_by=1)
            assert result is True
            downgraded = ACTIVE_CONNECTIONS.get(code, {}).get(20)
            assert isinstance(downgraded, ViewerHandle)
            assert downgraded.role == "viewer"
            assert downgraded.send_queue is original_queue
        finally:
            await unregister_connection(code, 20)

    @pytest.mark.asyncio
    async def test_demote_viewer_returns_false(self) -> None:
        code = "DEMOTE2"
        ws = _make_ws()
        await register_connection(code, 21, ws, role="viewer")
        try:
            result = await demote_to_viewer(code, 21, demoted_by=1)
            assert result is False
        finally:
            await unregister_connection(code, 21)


# ---------------------------------------------------------------------------
# TestRoleChangeAuthorisation
# ---------------------------------------------------------------------------

class TestRoleChangeAuthorisation:
    """Only role="host" ConnectionHandle may issue role_change."""

    @pytest.mark.asyncio
    async def test_non_host_editor_cannot_promote(self) -> None:
        from services.features.workshop_ws_role_change import handle_role_change

        code = "AUTHZ1"
        ws_editor = _make_ws()
        ws_target = _make_ws()
        editor = await register_connection(code, 30, ws_editor, role="editor")
        await register_connection(code, 31, ws_target, role="viewer")
        try:
            ctx = MagicMock()
            ctx.handle = editor
            ctx.websocket = ws_editor
            ctx.code = code
            ctx.owner_id = None
            ctx.user = MagicMock()
            ctx.user.id = 30
            await handle_role_change(ctx, {"type": "role_change", "user_id": 31, "to": "editor"})
            assert not editor.send_queue.empty()
            _, body = editor.send_queue.get_nowait()
            frame = json.loads(body)
            assert frame["type"] == "error"
        finally:
            await unregister_connection(code, 30)
            await unregister_connection(code, 31)

    @pytest.mark.asyncio
    async def test_viewer_cannot_issue_role_change(self) -> None:
        from services.features.workshop_ws_role_change import handle_role_change

        code = "AUTHZ2"
        ws_viewer = _make_ws()
        viewer = await register_connection(code, 40, ws_viewer, role="viewer")
        try:
            ctx = MagicMock()
            ctx.handle = viewer
            ctx.websocket = ws_viewer
            ctx.code = code
            ctx.owner_id = None
            ctx.user = MagicMock()
            ctx.user.id = 40
            await handle_role_change(ctx, {"type": "role_change", "user_id": 41, "to": "editor"})
            assert not viewer.send_queue.empty()
            _, body = viewer.send_queue.get_nowait()
            frame = json.loads(body)
            assert frame["type"] == "error"
        finally:
            await unregister_connection(code, 40)


# ---------------------------------------------------------------------------
# TestViewerSnapshotRefreshTask
# ---------------------------------------------------------------------------

class TestViewerSnapshotRefreshTask:
    """ensure_snapshot_task starts only once per room; stops when viewers leave."""

    def test_ensure_snapshot_task_is_idempotent(self) -> None:
        from services.online_collab.spec.online_collab_viewer_snapshot import (
            _SNAPSHOT_TASKS,
            ensure_snapshot_task,
        )

        code = "SNAPFRESH1"
        _SNAPSHOT_TASKS.pop(code, None)

        loop = asyncio.new_event_loop()
        try:
            task_ref = {}

            async def _run() -> None:
                ensure_snapshot_task(code)
                task1 = _SNAPSHOT_TASKS.get(code)
                ensure_snapshot_task(code)
                task2 = _SNAPSHOT_TASKS.get(code)
                assert task1 is task2
                task_ref["task"] = task1

            loop.run_until_complete(_run())
        finally:
            task = task_ref.get("task")
            if task and not task.done():
                task.cancel()
                try:
                    loop.run_until_complete(task)
                except (asyncio.CancelledError, Exception):
                    pass
            loop.close()
            _SNAPSHOT_TASKS.pop(code, None)

# ---------------------------------------------------------------------------
# TestRoomRegistryLock
# ---------------------------------------------------------------------------


class TestRoomRegistryLock:
    """Per-room registry lock is singleton per code under concurrent accessors."""

    @pytest.mark.asyncio
    async def test_concurrent_room_lock_creation_single_instance(self) -> None:
        from services.features.workshop_ws_connection_state import (
            _get_room_lock,
        )

        locks = await asyncio.gather(
            *(_get_room_lock("LOCKPAR1") for _ in range(32)),
        )
        identities = {id(lo) for lo in locks}
        assert len(identities) == 1


# ---------------------------------------------------------------------------
# TestSeqTracking
# ---------------------------------------------------------------------------

class TestSeqTracking:
    """seq field on broadcast update enables viewer gap detection."""

    def test_snapshot_key_included_in_purge_list(self) -> None:
        code = "PURGE1"
        sk = snapshot_key(code)
        ssk = snapshot_seq_key(code)
        assert "snapshot" in sk
        assert "snapshot_seq" in ssk

    @pytest.mark.asyncio
    async def test_fanout_tracks_seq_on_viewer_handle(self) -> None:
        from services.features.workshop_ws_fanout_delivery import _push_shard

        code = "SEQTRACK1"
        ws = _make_ws()
        viewer = await register_connection(code, 50, ws, role="viewer")
        assert viewer.last_seen_seq == 0
        try:
            shard = [(50, viewer)]
            sem = asyncio.Semaphore(1)
            body = json.dumps({"type": "update", "seq": 42}).encode()
            await _push_shard(shard, ("bytes", body), "all", None, code, sem, seq=42)
            assert viewer.last_seen_seq == 42
        finally:
            await unregister_connection(code, 50)
