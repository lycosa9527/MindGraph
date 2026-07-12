"""Cross-worker Redis relay for verified diagram mutation acks.

Pending mutation futures are process-local. When the desktop canvas owner WebSocket
lives on another Uvicorn worker, its ``diagram_mutation_ack`` cannot complete the
future on the mobile ingress worker — publish on the Kitty control channel so the
waiting worker can finish the verified-edit wait.

Diagram *apply* and canvas *actions* use Redis ``desktop_wake`` SSE to the browser
(not this module).

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
from services.diagram_edit.ack import complete_mutation_ack_from_client
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
from services.kitty.infra.control.kitty_observability import kitty_extra
from services.kitty.infra.control.kitty_workflow_trace import kitty_wf_log
from services.redis.redis_async_client import get_async_redis

logger = logging.getLogger(__name__)

KITTY_CONTROL_ACTION_MUTATION_ACK = "mutation_ack"
KITTY_CONTROL_REASON_MUTATION_ACK = "mutation_ack"


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


async def publish_mutation_ack_relay(ack_payload: Dict[str, Any]) -> bool:
    """Fan out an orphan ``diagram_mutation_ack`` so the waiting worker can complete it."""
    mutation_id = ack_payload.get("mutation_id")
    if not isinstance(mutation_id, str) or not mutation_id.strip():
        return False
    if not getattr(config, "DEBUG", True) and get_kitty_control_shared_secret() is None:
        record_kitty_control_publish_failure()
        return False
    redis = get_async_redis()
    if redis is None:
        record_kitty_control_publish_failure()
        return False
    scope = "mutation_ack"
    user_id = 0
    payload: Dict[str, Any] = {
        "v": KITTY_CONTROL_PAYLOAD_VERSION,
        "origin": get_kitty_control_instance_id(),
        "action": KITTY_CONTROL_ACTION_MUTATION_ACK,
        "scope": scope,
        "user_id": user_id,
        "reason": KITTY_CONTROL_REASON_MUTATION_ACK,
        "ack": dict(ack_payload),
    }
    auth = _sign(scope, user_id, KITTY_CONTROL_REASON_MUTATION_ACK)
    if auth:
        payload["auth"] = auth
    try:
        await redis.publish(kitty_control_channel(), json.dumps(payload, ensure_ascii=False))
        record_kitty_control_publish_success()
        return True
    except (RedisError, TypeError, ValueError) as exc:
        record_kitty_control_publish_failure()
        logger.warning(
            "[KittyMutationAckRelay] publish failed: %s",
            exc,
            extra=kitty_extra(
                "mutation_ack_relay_publish_error",
                error_type=type(exc).__name__,
            ),
        )
        return False


async def handle_mutation_ack_relay(envelope: Dict[str, Any]) -> bool:
    """Complete a local pending mutation future from a relayed ack."""
    if not _auth_ok(
        envelope,
        scope="mutation_ack",
        user_id=0,
        reason=KITTY_CONTROL_REASON_MUTATION_ACK,
    ):
        record_kitty_control_message_ignored()
        return False
    ack = envelope.get("ack")
    if not isinstance(ack, dict):
        record_kitty_control_message_ignored()
        return False
    matched = complete_mutation_ack_from_client(ack, allow_relay=False)
    if not matched:
        record_kitty_control_message_ignored()
        return False
    mutation_id = ack.get("mutation_id")
    kitty_wf_log(
        "diagram_ack",
        "relay_matched",
        action=str(mutation_id)[:12] if isinstance(mutation_id, str) else None,
    )
    return True
