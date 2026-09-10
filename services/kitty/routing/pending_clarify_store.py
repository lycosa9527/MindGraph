"""Redis persist for armed Kitty clarify-option picks.

In-memory ``voice_sessions`` drop pending options on WebSocket reconnect.
Store the armed commands by user + diagram scope so a tap still dispatches.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any, Dict, List, Optional, Tuple

from redis.exceptions import RedisError

from services.kitty.infra.redis.kitty_redis_keys import (
    kitty_pending_clarify_key,
    kitty_pending_intent_slot_key,
    kitty_redis_ttl_seconds,
)
from services.redis.redis_async_client import get_async_redis

logger = logging.getLogger(__name__)

_ALLOWED_OPTION_ACTIONS = frozenset(
    {
        "add_node",
        "update_center",
        "update_node",
        "delete_node",
        "auto_complete_branch",
        "auto_complete",
        "ask_followup",
        "decline_branch_autocomplete",
    }
)
_ALLOWED_SLOT_ACTIONS = frozenset(
    {
        "add_node",
        "update_center",
        "update_node",
        "delete_node",
        "auto_complete_branch",
    }
)
_SLOT_KEYS = ("action", "node_id", "parent_ref", "side", "followup")
_CMD_KEYS = (
    "action",
    "target",
    "node_id",
    "node_identifier",
    "node_label",
    "parent_id",
    "parent_ref",
    "side",
    "new_text",
    "text",
    "slot_action",
    "followup",
    "confidence",
)


def _session_owner(session: Dict[str, Any]) -> Tuple[Optional[int], str]:
    scope = str(session.get("diagram_session_id") or "").strip()
    raw = session.get("user_id")
    if raw is None:
        return None, scope
    try:
        user_id = int(raw)
    except (TypeError, ValueError):
        return None, scope
    if user_id <= 0 or not scope:
        return None, scope
    return user_id, scope


def _clip_str(value: Any, *, max_len: int = 240) -> Optional[str]:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if len(text) > max_len:
        return text[: max_len - 1] + "…"
    return text


def sanitize_pending_clarify(raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Keep a bounded pending payload safe to store and restore."""
    commands_raw = raw.get("option_commands")
    if not isinstance(commands_raw, list):
        return None
    commands: List[Dict[str, Any]] = []
    for item in commands_raw[:3]:
        if not isinstance(item, dict):
            continue
        cmd: Dict[str, Any] = {}
        for key in _CMD_KEYS:
            if key not in item:
                continue
            value = item.get(key)
            if isinstance(value, (int, float, bool)):
                cmd[key] = value
                continue
            clipped = _clip_str(value)
            if clipped is not None:
                cmd[key] = clipped
        action = str(cmd.get("action") or "").strip()
        if action in _ALLOWED_OPTION_ACTIONS:
            cmd["action"] = action
            commands.append(cmd)
    if len(commands) < 2:
        return None

    labels: List[str] = []
    raw_labels = raw.get("options")
    if isinstance(raw_labels, list):
        for item in raw_labels:
            clipped = _clip_str(item, max_len=120)
            if clipped is not None:
                labels.append(clipped)
            if len(labels) >= 3:
                break

    pending: Dict[str, Any] = {
        "option_commands": commands,
        "options": labels,
    }
    question = _clip_str(raw.get("question"), max_len=240)
    if question:
        pending["question"] = question
    seed = _clip_str(raw.get("seed_target"), max_len=120)
    if seed:
        pending["seed_target"] = seed
    return pending


async def persist_pending_clarify_payload(
    session: Optional[Dict[str, Any]],
    pending: Optional[Dict[str, Any]],
) -> None:
    """Write the armed pending payload, or delete the key when nothing is armed."""
    if pending is None:
        await delete_pending_clarify_payload(session)
        return
    if not isinstance(session, dict):
        return
    user_id, scope = _session_owner(session)
    if user_id is None:
        return
    payload = sanitize_pending_clarify(pending)
    if payload is None:
        await delete_pending_clarify_payload(session)
        return
    redis = get_async_redis()
    if redis is None:
        return
    try:
        await redis.set(
            kitty_pending_clarify_key(user_id, scope),
            json.dumps(payload, ensure_ascii=False),
            ex=kitty_redis_ttl_seconds(),
        )
    except (RedisError, TypeError, ValueError) as exc:
        logger.warning("[PendingClarify] persist failed scope=%s: %s", scope[:16], exc)


async def load_pending_clarify_payload(
    session: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Return the sanitized Redis payload, or None."""
    if not isinstance(session, dict):
        return None
    user_id, scope = _session_owner(session)
    if user_id is None:
        return None
    redis = get_async_redis()
    if redis is None:
        return None
    try:
        raw = await redis.get(kitty_pending_clarify_key(user_id, scope))
    except RedisError as exc:
        logger.warning("[PendingClarify] restore failed scope=%s: %s", scope[:16], exc)
        return None
    if not raw:
        return None
    text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    if not isinstance(parsed, dict):
        return None
    return sanitize_pending_clarify(parsed)


async def delete_pending_clarify_payload(session: Optional[Dict[str, Any]]) -> None:
    """Drop the Redis copy so a stale pick cannot fire after the user moved on."""
    await _delete_owner_key(session, kitty_pending_clarify_key)


def sanitize_pending_intent_slot(raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Keep a follow-up slot bounded and limited to value-slot edits."""
    action = str(raw.get("action") or "").strip()
    if action not in _ALLOWED_SLOT_ACTIONS:
        return None
    slot: Dict[str, Any] = {"action": action}
    for key in _SLOT_KEYS:
        if key == "action":
            continue
        clipped = _clip_str(raw.get(key), max_len=240)
        if clipped is not None:
            slot[key] = clipped
    return slot


async def persist_pending_intent_slot_payload(
    session: Optional[Dict[str, Any]],
    slot: Optional[Dict[str, Any]],
) -> None:
    """Write the armed follow-up slot, or delete the key when nothing is armed."""
    if slot is None:
        await delete_pending_intent_slot_payload(session)
        return
    payload = sanitize_pending_intent_slot(slot)
    if payload is None:
        await delete_pending_intent_slot_payload(session)
        return
    await _set_owner_json(session, kitty_pending_intent_slot_key, payload)


async def load_pending_intent_slot_payload(
    session: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Return the sanitized follow-up slot, or None."""
    parsed = await _get_owner_json(session, kitty_pending_intent_slot_key)
    if parsed is None:
        return None
    return sanitize_pending_intent_slot(parsed)


async def delete_pending_intent_slot_payload(session: Optional[Dict[str, Any]]) -> None:
    """Drop the Redis follow-up slot after it is consumed or cancelled."""
    await _delete_owner_key(session, kitty_pending_intent_slot_key)


async def migrate_pending_kitty_keys(
    user_id: int,
    from_scope: str,
    to_scope: str,
) -> None:
    """Move armed clarify + follow-up keys when a diagram scope is remapped."""
    source = str(from_scope or "").strip()
    target = str(to_scope or "").strip()
    if user_id <= 0 or not source or not target or source == target:
        return
    redis = get_async_redis()
    if redis is None:
        return
    ttl = kitty_redis_ttl_seconds()
    for key_fn in (kitty_pending_clarify_key, kitty_pending_intent_slot_key):
        source_key = key_fn(user_id, source)
        target_key = key_fn(user_id, target)
        try:
            raw = await redis.get(source_key)
            if raw:
                await redis.set(target_key, raw, ex=ttl)
            await redis.delete(source_key)
        except RedisError as exc:
            logger.warning(
                "[PendingClarify] migrate failed %s->%s: %s",
                source[:16],
                target[:16],
                exc,
            )


async def _set_owner_json(
    session: Optional[Dict[str, Any]],
    key_fn: Callable[[int, str], str],
    payload: Dict[str, Any],
) -> None:
    """Write a JSON payload under the owner-scoped Redis key."""
    if not isinstance(session, dict):
        return
    user_id, scope = _session_owner(session)
    if user_id is None:
        return
    redis = get_async_redis()
    if redis is None:
        return
    try:
        await redis.set(
            key_fn(user_id, scope),
            json.dumps(payload, ensure_ascii=False),
            ex=kitty_redis_ttl_seconds(),
        )
    except (RedisError, TypeError, ValueError) as exc:
        logger.warning("[PendingClarify] persist failed scope=%s: %s", scope[:16], exc)


async def _get_owner_json(
    session: Optional[Dict[str, Any]],
    key_fn: Callable[[int, str], str],
) -> Optional[Dict[str, Any]]:
    """Read a JSON object from the owner-scoped Redis key."""
    if not isinstance(session, dict):
        return None
    user_id, scope = _session_owner(session)
    if user_id is None:
        return None
    redis = get_async_redis()
    if redis is None:
        return None
    try:
        raw = await redis.get(key_fn(user_id, scope))
    except RedisError as exc:
        logger.warning("[PendingClarify] restore failed scope=%s: %s", scope[:16], exc)
        return None
    if not raw:
        return None
    text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    return parsed if isinstance(parsed, dict) else None


async def _delete_owner_key(
    session: Optional[Dict[str, Any]],
    key_fn: Callable[[int, str], str],
) -> None:
    """Delete the owner-scoped Redis key."""
    if not isinstance(session, dict):
        return
    user_id, scope = _session_owner(session)
    if user_id is None:
        return
    redis = get_async_redis()
    if redis is None:
        return
    try:
        await redis.delete(key_fn(user_id, scope))
    except RedisError as exc:
        logger.warning("[PendingClarify] delete failed scope=%s: %s", scope[:16], exc)
