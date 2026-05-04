"""Message handlers for canvas collaboration WebSocket (public facade)."""

from typing import Any, Dict, List

from routers.api import workshop_ws_handlers_presence as _presence
from routers.api.workshop_ws_handlers_core import (
    CollabWsContext,
    _EDITOR_HANDLERS,
    _MSG_HANDLERS,
    _VIEWER_HANDLERS,
    _collab_jwt_revalidate_interval_sec,
    _ctx_send,
    _handle_join_repeat,
    _handle_ping,
    _handle_resync,
    run_canvas_collab_receive_loop,
)
from routers.api.workshop_ws_handlers_update import handle_update as _handle_update

_NODE_EDIT_DEDUP_EVICT_COUNT = _presence._NODE_EDIT_DEDUP_EVICT_COUNT
_NODE_EDIT_DEDUP_MAX_ENTRIES = _presence._NODE_EDIT_DEDUP_MAX_ENTRIES
_NODE_EDIT_DEDUP_WINDOW_SEC = _presence._NODE_EDIT_DEDUP_WINDOW_SEC
_PARTICIPANTS_WITH_NAMES_CAP = _presence._PARTICIPANTS_WITH_NAMES_CAP
_USERNAME_CACHE_MAX = _presence._USERNAME_CACHE_MAX
_USERNAME_CACHE_TTL_SEC = _presence._USERNAME_CACHE_TTL_SEC
_node_editing_dedup_cache = _presence._node_editing_dedup_cache
_username_cache = _presence._username_cache
active_editors = _presence.active_editors
broadcast_to_all = _presence.broadcast_to_all
broadcast_to_others = _presence.broadcast_to_others
is_ws_fanout_enabled = _presence.is_ws_fanout_enabled
redis_user_cache = _presence.redis_user_cache


def _sync_presence_test_hooks() -> None:
    _presence.broadcast_to_all = broadcast_to_all
    _presence.broadcast_to_others = broadcast_to_others
    _presence.is_ws_fanout_enabled = is_ws_fanout_enabled
    _presence.redis_user_cache = redis_user_cache


def _evict_username_cache() -> None:
    _presence._evict_username_cache()


async def _resolve_participant_name(pid: int) -> Dict[str, Any]:
    _sync_presence_test_hooks()
    return await _presence._resolve_participant_name(pid)


async def build_participants_with_names(
    participant_ids: List[int],
) -> List[Dict[str, Any]]:
    _sync_presence_test_hooks()
    return await _presence.build_participants_with_names(participant_ids)


async def _handle_node_editing(ctx: Any, message: Dict[str, Any]) -> None:
    _sync_presence_test_hooks()
    await _presence._handle_node_editing(ctx, message)


async def _handle_node_editing_batch(ctx: Any, message: Dict[str, Any]) -> None:
    _sync_presence_test_hooks()
    await _presence._handle_node_editing_batch(ctx, message)


async def _handle_node_selected(ctx: Any, message: Dict[str, Any]) -> None:
    _sync_presence_test_hooks()
    await _presence._handle_node_selected(ctx, message)


async def _handle_claim_node_edit(ctx: Any, message: Dict[str, Any]) -> None:
    _sync_presence_test_hooks()
    await _presence._handle_claim_node_edit(ctx, message)


__all__ = [
    "CollabWsContext",
    "_EDITOR_HANDLERS",
    "_MSG_HANDLERS",
    "_NODE_EDIT_DEDUP_EVICT_COUNT",
    "_NODE_EDIT_DEDUP_MAX_ENTRIES",
    "_NODE_EDIT_DEDUP_WINDOW_SEC",
    "_PARTICIPANTS_WITH_NAMES_CAP",
    "_USERNAME_CACHE_MAX",
    "_USERNAME_CACHE_TTL_SEC",
    "_VIEWER_HANDLERS",
    "_collab_jwt_revalidate_interval_sec",
    "_ctx_send",
    "_evict_username_cache",
    "_handle_claim_node_edit",
    "_handle_join_repeat",
    "_handle_node_editing",
    "_handle_node_editing_batch",
    "_handle_node_selected",
    "_handle_ping",
    "_handle_resync",
    "_handle_update",
    "_node_editing_dedup_cache",
    "_resolve_participant_name",
    "_username_cache",
    "active_editors",
    "broadcast_to_all",
    "broadcast_to_others",
    "build_participants_with_names",
    "is_ws_fanout_enabled",
    "redis_user_cache",
    "run_canvas_collab_receive_loop",
]
