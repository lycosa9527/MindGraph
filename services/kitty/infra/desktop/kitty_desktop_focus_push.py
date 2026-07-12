"""Push desktop library focus to mobile Kitty WebSockets (local + cross-worker).

Redis ``kitty:desktop_focus:{user_id}`` remains the source of truth. Local WS push
covers same-worker mobile; Redis control ``desktop_focus`` relays to other workers.

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
from services.kitty.context.messaging import safe_websocket_send
from services.kitty.infra.control.kitty_control_channel import (
    KITTY_CONTROL_PAYLOAD_VERSION,
    get_kitty_control_instance_id,
    kitty_control_channel,
)
from services.kitty.infra.control.kitty_control_secret import get_kitty_control_shared_secret
from services.kitty.infra.control.kitty_observability import kitty_extra
from services.kitty.infra.control.kitty_workflow_trace import kitty_wf_log
from services.kitty.session.runtime_state import voice_sessions
from services.redis.redis_async_client import get_async_redis

logger = logging.getLogger(__name__)

KITTY_CONTROL_ACTION_DESKTOP_FOCUS = "desktop_focus"
KITTY_CONTROL_REASON_DESKTOP_FOCUS = "desktop_focus"
KITTY_CONTROL_SCOPE_DESKTOP_FOCUS = "desktop_focus"


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


def _focus_body(
    diagram_library_id: Optional[str],
    updated_at: Optional[int],
) -> Dict[str, Any]:
    return {
        "type": "desktop_focus_update",
        "diagram_library_id": diagram_library_id,
        "updated_at": updated_at,
    }


async def push_kitty_desktop_focus_to_local_mobile(
    user_id: int,
    diagram_library_id: Optional[str],
    updated_at: Optional[int],
) -> int:
    """Send ``desktop_focus_update`` to mobile-lane Kitty sockets on this worker."""
    body = _focus_body(diagram_library_id, updated_at)
    sent = 0
    for _sid, sess in list(voice_sessions.items()):
        if not isinstance(sess, dict):
            continue
        if sess.get("_kitty_client_lane") != "mobile":
            continue
        raw_uid = sess.get("user_id")
        if raw_uid is None:
            continue
        try:
            sess_uid = int(raw_uid)
        except (TypeError, ValueError):
            continue
        if sess_uid != int(user_id):
            continue
        websocket = sess.get("_client_websocket")
        if websocket is None:
            continue
        ok = await safe_websocket_send(websocket, body)
        if ok:
            sent += 1
    if sent:
        kitty_wf_log(
            "ws_out",
            "desktop_focus_push",
            user_id=user_id,
            action="desktop_focus",
        )
    return sent


async def publish_desktop_focus_relay(
    user_id: int,
    diagram_library_id: Optional[str],
    updated_at: Optional[int],
) -> bool:
    """Fan out focus so other workers can push to their local mobile sockets."""
    if not getattr(config, "DEBUG", True) and get_kitty_control_shared_secret() is None:
        record_kitty_control_publish_failure()
        return False
    redis = get_async_redis()
    if redis is None:
        record_kitty_control_publish_failure()
        return False
    scope = KITTY_CONTROL_SCOPE_DESKTOP_FOCUS
    reason = KITTY_CONTROL_REASON_DESKTOP_FOCUS
    payload: Dict[str, Any] = {
        "v": KITTY_CONTROL_PAYLOAD_VERSION,
        "origin": get_kitty_control_instance_id(),
        "action": KITTY_CONTROL_ACTION_DESKTOP_FOCUS,
        "scope": scope,
        "user_id": int(user_id),
        "reason": reason,
        "diagram_library_id": diagram_library_id,
        "updated_at": updated_at,
    }
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
            "[KittyDesktopFocus] relay publish failed user=%s: %s",
            user_id,
            exc,
            extra=kitty_extra(
                "desktop_focus_relay_publish_error",
                user_id=int(user_id),
                error_type=type(exc).__name__,
            ),
        )
        return False


async def handle_desktop_focus_relay(envelope: Dict[str, Any]) -> bool:
    """Apply a relayed focus push on this worker (skip origin to avoid double-send)."""
    raw_uid = envelope.get("user_id")
    try:
        user_id = int(raw_uid) if raw_uid is not None else None
    except (TypeError, ValueError):
        user_id = None
    if user_id is None:
        record_kitty_control_message_ignored()
        return False
    if not _auth_ok(
        envelope,
        scope=KITTY_CONTROL_SCOPE_DESKTOP_FOCUS,
        user_id=user_id,
        reason=KITTY_CONTROL_REASON_DESKTOP_FOCUS,
    ):
        record_kitty_control_message_ignored()
        return False
    origin = envelope.get("origin")
    if isinstance(origin, str) and origin == get_kitty_control_instance_id():
        record_kitty_control_message_ignored()
        return False
    lib = envelope.get("diagram_library_id")
    lib_id = lib if isinstance(lib, str) and lib.strip() else None
    raw_ts = envelope.get("updated_at")
    if isinstance(raw_ts, bool) or raw_ts is None:
        updated_at: Optional[int] = None
    elif isinstance(raw_ts, (int, float)):
        updated_at = int(raw_ts)
    else:
        updated_at = None
    sent = await push_kitty_desktop_focus_to_local_mobile(user_id, lib_id, updated_at)
    return sent > 0


async def notify_kitty_desktop_focus_changed(
    user_id: int,
    diagram_library_id: Optional[str],
    updated_at: Optional[int],
) -> None:
    """Local mobile push + Redis control relay for cross-worker mobile Kitty."""
    await push_kitty_desktop_focus_to_local_mobile(user_id, diagram_library_id, updated_at)
    await publish_desktop_focus_relay(user_id, diagram_library_id, updated_at)
