"""Message handlers for canvas collaboration WebSocket (public facade)."""

from typing import Any, Dict, List

from routers.api import workshop_ws_handlers_presence as presence_module
from routers.api.workshop_ws_handlers_core import (
    EDITOR_HANDLERS,
    MSG_HANDLERS,
    VIEWER_HANDLERS,
    CollabWsContext,
    collab_jwt_revalidate_interval_sec,
    ctx_send,
    handle_join_repeat,
    handle_ping,
    handle_resync,
    run_canvas_collab_receive_loop,
)
from routers.api.workshop_ws_handlers_presence import (
    NODE_EDIT_DEDUP_EVICT_COUNT,
    NODE_EDIT_DEDUP_MAX_ENTRIES,
    NODE_EDIT_DEDUP_WINDOW_SEC,
    PARTICIPANTS_WITH_NAMES_CAP,
    USERNAME_CACHE_MAX,
    USERNAME_CACHE_TTL_SEC,
    active_editors,
    build_participants_with_names as presence_build_participants_with_names,
    evict_username_cache,
    handle_claim_node_edit as presence_handle_claim_node_edit,
    handle_node_editing as presence_handle_node_editing,
    handle_node_editing_batch as presence_handle_node_editing_batch,
    handle_node_selected as presence_handle_node_selected,
    node_editing_dedup_cache,
    resolve_participant_name as presence_resolve_participant_name,
    username_cache,
)
from routers.api.workshop_ws_handlers_update import handle_update

broadcast_to_all = presence_module.broadcast_to_all
broadcast_to_others = presence_module.broadcast_to_others
is_ws_fanout_enabled = presence_module.is_ws_fanout_enabled
redis_user_cache = presence_module.redis_user_cache


def sync_presence_test_hooks() -> None:
    """Mirror facade test doubles onto the presence module."""
    presence_module.broadcast_to_all = broadcast_to_all
    presence_module.broadcast_to_others = broadcast_to_others
    presence_module.is_ws_fanout_enabled = is_ws_fanout_enabled
    presence_module.redis_user_cache = redis_user_cache


async def resolve_participant_name(pid: int) -> Dict[str, Any]:
    """Resolve participant name."""
    sync_presence_test_hooks()
    return await presence_resolve_participant_name(pid)


async def build_participants_with_names(
    participant_ids: List[int],
) -> List[Dict[str, Any]]:
    """Build participants with names."""
    sync_presence_test_hooks()
    return await presence_build_participants_with_names(participant_ids)


async def handle_node_editing(ctx: Any, message: Dict[str, Any]) -> None:
    """Handle node editing."""
    sync_presence_test_hooks()
    await presence_handle_node_editing(ctx, message)


async def handle_node_editing_batch(ctx: Any, message: Dict[str, Any]) -> None:
    """Handle node editing batch."""
    sync_presence_test_hooks()
    await presence_handle_node_editing_batch(ctx, message)


async def handle_node_selected(ctx: Any, message: Dict[str, Any]) -> None:
    """Handle node selected."""
    sync_presence_test_hooks()
    await presence_handle_node_selected(ctx, message)


async def handle_claim_node_edit(ctx: Any, message: Dict[str, Any]) -> None:
    """Handle claim node edit."""
    sync_presence_test_hooks()
    await presence_handle_claim_node_edit(ctx, message)


__all__ = [
    "CollabWsContext",
    "EDITOR_HANDLERS",
    "MSG_HANDLERS",
    "NODE_EDIT_DEDUP_EVICT_COUNT",
    "NODE_EDIT_DEDUP_MAX_ENTRIES",
    "NODE_EDIT_DEDUP_WINDOW_SEC",
    "PARTICIPANTS_WITH_NAMES_CAP",
    "USERNAME_CACHE_MAX",
    "USERNAME_CACHE_TTL_SEC",
    "VIEWER_HANDLERS",
    "active_editors",
    "broadcast_to_all",
    "broadcast_to_others",
    "build_participants_with_names",
    "collab_jwt_revalidate_interval_sec",
    "ctx_send",
    "evict_username_cache",
    "handle_claim_node_edit",
    "handle_join_repeat",
    "handle_node_editing",
    "handle_node_editing_batch",
    "handle_node_selected",
    "handle_ping",
    "handle_resync",
    "handle_update",
    "is_ws_fanout_enabled",
    "node_editing_dedup_cache",
    "redis_user_cache",
    "resolve_participant_name",
    "run_canvas_collab_receive_loop",
    "sync_presence_test_hooks",
    "username_cache",
]
