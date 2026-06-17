"""Redis pub/sub wake events for desktop Kitty SSE (mobile connect / disconnect)."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from redis.exceptions import RedisError

from services.kitty.infra.control.kitty_workflow_trace import kitty_wf_log, summarize_diagram_update
from services.kitty.infra.redis.kitty_redis_keys import kitty_desktop_wake_channel
from services.redis.redis_async_client import get_async_redis

logger = logging.getLogger(__name__)

_EVENT_TYPE = "mobile_active"


def build_kitty_desktop_wake_payload(mobile_state: Dict[str, Any]) -> str:
    """JSON SSE payload for a ``mobile_active`` snapshot."""
    body: Dict[str, Any] = {"type": _EVENT_TYPE}
    active = mobile_state.get("active")
    body["active"] = active is True
    scopes = mobile_state.get("scopes")
    if isinstance(scopes, list):
        body["scopes"] = [str(item) for item in scopes if isinstance(item, str)]
    else:
        body["scopes"] = []
    primary = mobile_state.get("primary_scope")
    body["primary_scope"] = primary if isinstance(primary, str) and primary.strip() else None
    return json.dumps(body, ensure_ascii=False)


async def publish_kitty_desktop_wake(user_id: int, mobile_state: Dict[str, Any]) -> None:
    """Notify desktop SSE listeners that ``mobile_active`` changed for ``user_id``."""
    redis = get_async_redis()
    if redis is None:
        return
    channel = kitty_desktop_wake_channel(int(user_id))
    payload = build_kitty_desktop_wake_payload(mobile_state)
    try:
        await redis.publish(channel, payload)
    except (RedisError, TypeError, ValueError) as exc:
        logger.debug(
            "[KittyDesktopWake] publish failed user=%s: %s",
            user_id,
            exc,
        )


async def publish_kitty_desktop_action_pending(user_id: int) -> None:
    """Wake desktop tabs to drain an explicit mobile REST enqueue (library pick, etc.)."""
    redis = get_async_redis()
    if redis is None:
        return
    channel = kitty_desktop_wake_channel(int(user_id))
    payload = json.dumps({"type": "desktop_action_pending"}, ensure_ascii=False)
    try:
        await redis.publish(channel, payload)
        kitty_wf_log("sse_wake", "desktop_action_pending", user_id=user_id)
    except (RedisError, TypeError, ValueError) as exc:
        logger.debug(
            "[KittyDesktopWake] action_pending publish failed user=%s: %s",
            user_id,
            exc,
        )


async def publish_kitty_diagram_update(
    user_id: int,
    scope: str,
    message: Dict[str, Any],
) -> None:
    """Fan out voice ``diagram_update`` payloads to desktop SSE wake listeners."""
    redis = get_async_redis()
    if redis is None:
        return
    channel = kitty_desktop_wake_channel(int(user_id))
    body: Dict[str, Any] = {
        "type": "diagram_update",
        "scope": scope,
        "action": message.get("action"),
        "updates": message.get("updates"),
    }
    payload = json.dumps(body, ensure_ascii=False)
    try:
        await redis.publish(channel, payload)
        act = str(message.get("action") or "").strip()
        kitty_wf_log(
            "sse_fanout",
            summarize_diagram_update(act, message.get("updates")),
            scope=scope,
            user_id=user_id,
            action=act or None,
        )
    except (RedisError, TypeError, ValueError) as exc:
        logger.debug(
            "[KittyDesktopWake] diagram_update publish failed user=%s scope=%s: %s",
            user_id,
            scope,
            exc,
        )


async def publish_kitty_selection_update(
    user_id: int,
    scope: str,
    selected_nodes: list[str],
) -> None:
    """Fan out mobile click-wheel selection to desktop SSE wake listeners."""
    redis = get_async_redis()
    if redis is None:
        return
    channel = kitty_desktop_wake_channel(int(user_id))
    body: Dict[str, Any] = {
        "type": "selection_update",
        "scope": scope,
        "selected_nodes": selected_nodes,
    }
    payload = json.dumps(body, ensure_ascii=False)
    try:
        await redis.publish(channel, payload)
        sel = selected_nodes[0] if selected_nodes else "—"
        kitty_wf_log(
            "selection_fanout",
            f"nodes={len(selected_nodes)} first={sel}",
            scope=scope,
            user_id=user_id,
            action="select_node",
        )
    except (RedisError, TypeError, ValueError) as exc:
        logger.debug(
            "[KittyDesktopWake] selection_update publish failed user=%s scope=%s: %s",
            user_id,
            scope,
            exc,
        )
    node_detail = selected_nodes[0] if selected_nodes else None
    await publish_kitty_voice_command_log(
        int(user_id),
        scope,
        action="select_node",
        detail=node_detail,
    )


async def publish_kitty_voice_command_log(
    user_id: int,
    scope: str,
    *,
    action: str,
    detail: Optional[str] = None,
) -> None:
    """Fan out a human-readable voice command entry for desktop command log UI."""
    redis = get_async_redis()
    if redis is None:
        return
    act = str(action or "").strip()
    if not act:
        return
    channel = kitty_desktop_wake_channel(int(user_id))
    body: Dict[str, Any] = {
        "type": "voice_command",
        "scope": scope,
        "action": act,
    }
    if isinstance(detail, str) and detail.strip():
        body["detail"] = detail.strip()
    payload = json.dumps(body, ensure_ascii=False)
    try:
        await redis.publish(channel, payload)
        kitty_wf_log(
            "voice_command",
            detail or act,
            scope=scope,
            user_id=user_id,
            action=act,
        )
    except (RedisError, TypeError, ValueError) as exc:
        logger.debug(
            "[KittyDesktopWake] voice_command publish failed user=%s scope=%s: %s",
            user_id,
            scope,
            exc,
        )
