"""Kitty write-path fanout: live_context, conversation turns, session snapshots.

Local sockets plus Redis control relay (same bus as desktop focus). Relay
payloads stay small; receivers rebuild from Redis.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Any, Dict, Optional

from redis.exceptions import RedisError

from config.settings import config
from services.infrastructure.monitoring.ws_metrics import (
    record_kitty_control_message_ignored,
    record_kitty_control_publish_failure,
    record_kitty_control_publish_success,
)
from services.kitty.infra.control.kitty_control_channel import (
    KITTY_CONTROL_PAYLOAD_VERSION,
    get_kitty_control_instance_id,
    kitty_control_channel,
)
from services.kitty.infra.control.kitty_control_secret import get_kitty_control_shared_secret
from services.kitty.infra.control.kitty_lane_send import (
    iter_local_kitty_scopes,
    send_kitty_ws_json,
)
from services.kitty.infra.control.kitty_observability import kitty_extra
from services.kitty.infra.redis.kitty_session_redis import load_kitty_live_context
from services.kitty.session.manager.align import build_kitty_session_snapshot
from services.redis.redis_async_client import get_async_redis

logger = logging.getLogger(__name__)

KITTY_CONTROL_ACTION_LIVE_CONTEXT = "live_context_update"
KITTY_CONTROL_ACTION_CONVERSATION_TURN = "conversation_turn"
KITTY_CONTROL_ACTION_SESSION_SNAPSHOT = "session_snapshot"

KITTY_EVENT_RELAY_ACTIONS = frozenset(
    {
        KITTY_CONTROL_ACTION_LIVE_CONTEXT,
        KITTY_CONTROL_ACTION_CONVERSATION_TURN,
        KITTY_CONTROL_ACTION_SESSION_SNAPSHOT,
    }
)

# Focus-clear may run on an API worker with no local Kitty sockets. Other
# workers still need to rebuild pairing snapshots for their live lanes.
SESSION_SNAPSHOT_RELAY_ALL = "__all__"

_MOBILE_LANES = frozenset({"mobile"})
# Only unambiguous persist sources. ``asr`` is desktop ingress, not a Redis source.
_WRITER_EXCLUDE = {
    "mobile_ui": "mobile",
    "desktop_ui": "desktop",
    "ui_edit": "desktop",
    "ui_create": "desktop",
    "ui_reply": "desktop",
    "ui_queued": "desktop",
    "ui_failed": "desktop",
}


def _sign(scope: str, user_id: int, reason: str) -> Optional[str]:
    secret = get_kitty_control_shared_secret()
    if not secret:
        return None
    msg = f"{scope}:{user_id}:{reason}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()


def _auth_ok(envelope: Dict[str, Any], *, scope: str, user_id: int, reason: str) -> bool:
    secret = get_kitty_control_shared_secret()
    if not secret:
        return bool(getattr(config, "DEBUG", True))
    token = envelope.get("auth")
    if not isinstance(token, str) or not token:
        return False
    expected = _sign(scope, user_id, reason)
    if expected is None:
        return False
    return hmac.compare_digest(token, expected)


def live_context_ws_body(scope: str, live: Dict[str, Any]) -> Dict[str, Any]:
    """Same fields as GET ``/api/kitty/live_context/{scope}``."""
    return {
        "type": "live_context_update",
        "scope": scope,
        "ok": True,
        "updated_at": live.get("updated_at"),
        "diagram_type": live.get("diagram_type"),
        "active_panel": live.get("active_panel"),
        "diagram_data": live.get("diagram_data") or {},
        "selected_nodes": live.get("selected_nodes") or [],
        "selected_llm_model": live.get("selected_llm_model"),
    }


def conversation_turn_ws_body(scope: str, turn: Dict[str, Any]) -> Dict[str, Any]:
    """Compact persisted turn for the peer lane."""
    compact = {
        key: turn[key]
        for key in (
            "turn_id",
            "ts",
            "role",
            "content",
            "phase",
            "source",
            "request_id",
            "outcome",
            "action",
            "diagram_type",
            "command_detail",
        )
        if key in turn and turn[key] is not None
    }
    return {"type": "conversation_turn", "scope": scope, "turn": compact}


def session_snapshot_ws_body(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """Session Manager DTO for mobile/desktop pairing banners."""
    return {"type": "session_snapshot", "session": snapshot}


def _exclude_lane_for_source(source: Any) -> Optional[str]:
    if not isinstance(source, str):
        return None
    return _WRITER_EXCLUDE.get(source.strip().lower())


async def _publish_relay(
    action: str,
    user_id: int,
    *,
    scope: str,
    reason: str,
    extra: Optional[Dict[str, Any]] = None,
) -> bool:
    if not getattr(config, "DEBUG", True) and get_kitty_control_shared_secret() is None:
        record_kitty_control_publish_failure()
        return False
    redis = get_async_redis()
    if redis is None:
        record_kitty_control_publish_failure()
        return False
    payload: Dict[str, Any] = {
        "v": KITTY_CONTROL_PAYLOAD_VERSION,
        "origin": get_kitty_control_instance_id(),
        "action": action,
        "scope": scope,
        "user_id": int(user_id),
        "reason": reason,
    }
    if extra:
        payload.update(extra)
    auth = _sign(scope, int(user_id), reason)
    if auth:
        payload["auth"] = auth
    try:
        await redis.publish(kitty_control_channel(), json.dumps(payload, ensure_ascii=False))
        record_kitty_control_publish_success()
        return True
    except (RedisError, TypeError, ValueError) as exc:
        record_kitty_control_publish_failure()
        logger.warning(
            "[KittyEventPush] relay publish failed action=%s user=%s: %s",
            action,
            user_id,
            exc,
            extra=kitty_extra(
                "event_relay_publish_error",
                user_id=int(user_id),
                error_type=type(exc).__name__,
            ),
        )
        return False


def _parsed_user_id(envelope: Dict[str, Any]) -> Optional[int]:
    raw_uid = envelope.get("user_id")
    try:
        return int(raw_uid) if raw_uid is not None else None
    except (TypeError, ValueError):
        return None


def _relay_origin_is_local(envelope: Dict[str, Any]) -> bool:
    origin = envelope.get("origin")
    return isinstance(origin, str) and origin == get_kitty_control_instance_id()


async def notify_kitty_live_context_changed(
    user_id: int,
    scope: str,
    live: Dict[str, Any],
) -> None:
    """Push GET-shaped live_context to mobile-lane sockets on ``scope``."""
    scope_key = str(scope or "").strip()
    if not scope_key:
        return
    body = live_context_ws_body(scope_key, live)
    await send_kitty_ws_json(user_id, body, scope=scope_key, lanes=_MOBILE_LANES)
    await _publish_relay(
        KITTY_CONTROL_ACTION_LIVE_CONTEXT,
        user_id,
        scope=scope_key,
        reason=KITTY_CONTROL_ACTION_LIVE_CONTEXT,
        extra={"updated_at": live.get("updated_at")},
    )


async def notify_kitty_conversation_turn(
    user_id: int,
    scope: str,
    turn: Dict[str, Any],
) -> None:
    """Fan a persisted turn to peer-lane sockets on ``scope``."""
    scope_key = str(scope or "").strip()
    if not scope_key or not isinstance(turn, dict):
        return
    body = conversation_turn_ws_body(scope_key, turn)
    exclude = _exclude_lane_for_source(turn.get("source"))
    exclude_lanes = frozenset({exclude}) if exclude else None
    await send_kitty_ws_json(user_id, body, scope=scope_key, exclude_lanes=exclude_lanes)
    extra: Dict[str, Any] = {"turn": body["turn"]}
    if exclude:
        extra["exclude_lane"] = exclude
    await _publish_relay(
        KITTY_CONTROL_ACTION_CONVERSATION_TURN,
        user_id,
        scope=scope_key,
        reason=KITTY_CONTROL_ACTION_CONVERSATION_TURN,
        extra=extra,
    )


async def notify_kitty_session_snapshot_changed(
    user_id: int,
    scope: Optional[str] = None,
) -> None:
    """Rebuild and push Session Manager snapshots for local sockets + relay."""
    scope_key = str(scope or "").strip()
    await _push_session_snapshots_local(user_id, preferred_scope=scope_key or None)
    relay_scope = scope_key
    if not relay_scope:
        local_scopes = iter_local_kitty_scopes(user_id)
        relay_scope = local_scopes[0] if local_scopes else SESSION_SNAPSHOT_RELAY_ALL
    await _publish_relay(
        KITTY_CONTROL_ACTION_SESSION_SNAPSHOT,
        user_id,
        scope=relay_scope,
        reason=KITTY_CONTROL_ACTION_SESSION_SNAPSHOT,
    )


async def _push_session_snapshots_local(
    user_id: int,
    *,
    preferred_scope: Optional[str] = None,
) -> int:
    scopes = list(iter_local_kitty_scopes(user_id))
    if preferred_scope and preferred_scope != SESSION_SNAPSHOT_RELAY_ALL and preferred_scope not in scopes:
        scopes.append(preferred_scope)
    sent = 0
    for scope in scopes:
        snapshot = await build_kitty_session_snapshot(user_id, scope)
        body = session_snapshot_ws_body(snapshot.to_dict())
        sent += await send_kitty_ws_json(user_id, body, scope=scope)
    return sent


async def handle_live_context_relay(envelope: Dict[str, Any]) -> bool:
    """Rebuild live_context from Redis and push to this worker's mobile sockets."""
    user_id = _parsed_user_id(envelope)
    scope = envelope.get("scope")
    if user_id is None or not isinstance(scope, str) or not scope.strip():
        record_kitty_control_message_ignored()
        return False
    scope_key = scope.strip()
    if not _auth_ok(
        envelope,
        scope=scope_key,
        user_id=user_id,
        reason=KITTY_CONTROL_ACTION_LIVE_CONTEXT,
    ):
        record_kitty_control_message_ignored()
        return False
    if _relay_origin_is_local(envelope):
        record_kitty_control_message_ignored()
        return False
    live = await load_kitty_live_context(scope_key)
    if not isinstance(live, dict):
        return False
    body = live_context_ws_body(scope_key, live)
    sent = await send_kitty_ws_json(user_id, body, scope=scope_key, lanes=_MOBILE_LANES)
    return sent > 0


async def handle_conversation_turn_relay(envelope: Dict[str, Any]) -> bool:
    """Push a relayed compact turn to peer-lane sockets on this worker."""
    user_id = _parsed_user_id(envelope)
    scope = envelope.get("scope")
    turn = envelope.get("turn")
    if user_id is None or not isinstance(scope, str) or not scope.strip():
        record_kitty_control_message_ignored()
        return False
    if not isinstance(turn, dict):
        record_kitty_control_message_ignored()
        return False
    scope_key = scope.strip()
    if not _auth_ok(
        envelope,
        scope=scope_key,
        user_id=user_id,
        reason=KITTY_CONTROL_ACTION_CONVERSATION_TURN,
    ):
        record_kitty_control_message_ignored()
        return False
    if _relay_origin_is_local(envelope):
        record_kitty_control_message_ignored()
        return False
    body = conversation_turn_ws_body(scope_key, turn)
    exclude = envelope.get("exclude_lane")
    exclude_lanes = frozenset({exclude}) if isinstance(exclude, str) and exclude else None
    sent = await send_kitty_ws_json(user_id, body, scope=scope_key, exclude_lanes=exclude_lanes)
    return sent > 0


async def handle_session_snapshot_relay(envelope: Dict[str, Any]) -> bool:
    """Rebuild session snapshots for this worker's Kitty sockets."""
    user_id = _parsed_user_id(envelope)
    scope = envelope.get("scope")
    if user_id is None or not isinstance(scope, str) or not scope.strip():
        record_kitty_control_message_ignored()
        return False
    scope_key = scope.strip()
    if not _auth_ok(
        envelope,
        scope=scope_key,
        user_id=user_id,
        reason=KITTY_CONTROL_ACTION_SESSION_SNAPSHOT,
    ):
        record_kitty_control_message_ignored()
        return False
    if _relay_origin_is_local(envelope):
        record_kitty_control_message_ignored()
        return False
    sent = await _push_session_snapshots_local(user_id, preferred_scope=scope_key)
    return sent > 0
