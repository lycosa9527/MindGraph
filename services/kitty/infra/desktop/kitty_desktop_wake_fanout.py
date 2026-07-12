"""Redis pub/sub wake events for desktop Kitty SSE (mobile connect / disconnect).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

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
    """Fan out voice ``diagram_update`` payloads to desktop SSE wake listeners.

    Verified edits include ``mutation_id`` (and optional verify metadata). The
    desktop canvas owner applies those frames; observers must not re-apply.
    """
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
    mutation_id = message.get("mutation_id")
    if isinstance(mutation_id, str) and mutation_id.strip():
        body["mutation_id"] = mutation_id.strip()
        expected = message.get("expected_effect")
        if isinstance(expected, dict):
            body["expected_effect"] = expected
        before = message.get("before_fingerprint")
        if isinstance(before, dict):
            body["before_fingerprint"] = before
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


async def publish_kitty_canvas_action(
    user_id: int,
    scope: str,
    message: Dict[str, Any],
) -> bool:
    """
    Fan out a canvas ``action`` (auto_complete, etc.) to desktop SSE listeners.

    Used when the desktop canvas_owner WebSocket lives on another worker —
    Redis desktop_wake already reaches the browser regardless of WS affinity.
    """
    redis = get_async_redis()
    if redis is None:
        return False
    action = message.get("action")
    if not isinstance(action, str) or not action.strip():
        return False
    params = message.get("params")
    body: Dict[str, Any] = {
        "type": "canvas_action",
        "scope": scope,
        "action": action.strip(),
        "params": params if isinstance(params, dict) else {},
    }
    channel = kitty_desktop_wake_channel(int(user_id))
    payload = json.dumps(body, ensure_ascii=False)
    try:
        await redis.publish(channel, payload)
        kitty_wf_log(
            "sse_fanout",
            "canvas_action",
            scope=scope,
            user_id=user_id,
            action=action.strip(),
        )
        return True
    except (RedisError, TypeError, ValueError) as exc:
        logger.debug(
            "[KittyDesktopWake] canvas_action publish failed user=%s scope=%s: %s",
            user_id,
            scope,
            exc,
        )
        return False


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


_VALID_KITTY_LLM_MODELS = frozenset({"qwen", "deepseek", "doubao"})


def normalize_kitty_llm_model(raw: Any) -> Optional[str]:
    """Return qwen|deepseek|doubao, or None when value is absent/invalid/clear."""
    if raw is None:
        return None
    if not isinstance(raw, str):
        return None
    key = raw.strip().lower()
    if key in {"", "null", "none"}:
        return None
    if key in _VALID_KITTY_LLM_MODELS:
        return key
    return None


def kitty_llm_model_update_from_context(
    merged_ctx: Dict[str, Any],
) -> tuple[bool, Optional[str]]:
    """
    Parse ``selected_llm_model`` from a context patch.

    Returns ``(should_publish, model_or_none)``. When the key is present with a
    clear/null value, publishes a clear (``None``).
    """
    if "selected_llm_model" not in merged_ctx:
        return False, None
    raw = merged_ctx.get("selected_llm_model")
    if raw is None:
        return True, None
    if isinstance(raw, str) and raw.strip().lower() in {"", "null", "none"}:
        return True, None
    normalized = normalize_kitty_llm_model(raw)
    if normalized is None:
        return False, None
    return True, normalized


async def publish_kitty_llm_model_update(
    user_id: int,
    scope: str,
    selected_llm_model: Optional[str],
) -> None:
    """Fan out mobile LLM pill choice to desktop SSE wake listeners."""
    redis = get_async_redis()
    if redis is None:
        return
    channel = kitty_desktop_wake_channel(int(user_id))
    body: Dict[str, Any] = {
        "type": "llm_model_update",
        "scope": scope,
        "selected_llm_model": selected_llm_model,
    }
    payload = json.dumps(body, ensure_ascii=False)
    try:
        await redis.publish(channel, payload)
        kitty_wf_log(
            "llm_model_fanout",
            str(selected_llm_model or "cleared"),
            scope=scope,
            user_id=user_id,
            action="select_llm_model",
        )
    except (RedisError, TypeError, ValueError) as exc:
        logger.debug(
            "[KittyDesktopWake] llm_model_update publish failed user=%s scope=%s: %s",
            user_id,
            scope,
            exc,
        )
    await publish_kitty_voice_command_log(
        int(user_id),
        scope,
        action="select_llm_model",
        detail=selected_llm_model,
    )


_VALID_KITTY_VOICE_PHASES = frozenset({"listening", "speaking", "active"})


async def publish_kitty_voice_phase_update(
    user_id: int,
    scope: str,
    phase: str,
) -> None:
    """Fan out mobile Kitty mic/reply phase to desktop SSE wake listeners."""
    normalized = str(phase or "").strip().lower()
    if normalized not in _VALID_KITTY_VOICE_PHASES:
        return
    redis = get_async_redis()
    if redis is None:
        return
    channel = kitty_desktop_wake_channel(int(user_id))
    body: Dict[str, Any] = {
        "type": "voice_phase_update",
        "scope": scope,
        "phase": normalized,
    }
    payload = json.dumps(body, ensure_ascii=False)
    try:
        await redis.publish(channel, payload)
        kitty_wf_log(
            "voice_phase_fanout",
            normalized,
            scope=scope,
            user_id=user_id,
            action=normalized,
        )
    except (RedisError, TypeError, ValueError) as exc:
        logger.debug(
            "[KittyDesktopWake] voice_phase_update publish failed user=%s scope=%s: %s",
            user_id,
            scope,
            exc,
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
