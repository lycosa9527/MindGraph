"""
Redis pub/sub so shared-diagram spec snapshots reach every app worker.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from typing import Optional, TypedDict

from services.diagram_shares.queue import ShareTab, encode_tabs
from services.diagram_shares.rooms import (
    close_share_room,
    close_share_sockets_for_user,
    relay_share_spec,
)
from services.diagram_shares.seats import push_roster
from services.features.ws_redis_fanout_config import is_ws_fanout_enabled
from services.redis.redis_async_client import get_async_redis
from services.utils.error_types import JSON_PARSE_ERRORS, REDIS_ERRORS

logger = logging.getLogger(__name__)

SHARE_FANOUT_CHANNEL = "mg:ws:diagram-share"
_ACTIONS = frozenset({"spec", "kick", "close", "roster"})
_WORKER_ID = f"{os.getpid()}-{uuid.uuid4().hex[:8]}"


class ShareFanoutCommand(TypedDict):
    """One fan-out message: a spec snapshot, a user kick, or a room close."""

    action: str
    diagram_id: str
    from_tab: str
    body: str
    user_id: int
    worker: str


def share_fanout_worker_id() -> str:
    """Process id stamped on envelopes so this worker does not apply its own publish twice."""
    return _WORKER_ID


def _origin_secret() -> str:
    return os.getenv("COLLAB_FANOUT_ORIGIN_SECRET", "")


def _stamp(envelope: dict[str, str | int]) -> str:
    secret = _origin_secret()
    if secret:
        envelope["origin"] = secret
    return json.dumps(envelope)


def build_share_fanout_body(diagram_id: str, from_tab: str, body: str) -> str:
    """Spec envelope published on ``SHARE_FANOUT_CHANNEL``."""
    return _stamp(
        {
            "action": "spec",
            "diagram_id": diagram_id,
            "from_tab": from_tab,
            "body": body,
            "worker": _WORKER_ID,
        }
    )


def build_share_roster_body(diagram_id: str, body: str) -> str:
    """Roster envelope so every worker can push role changes down open SSE streams."""
    return _stamp(
        {
            "action": "roster",
            "diagram_id": diagram_id,
            "from_tab": "-",
            "body": body,
            "worker": _WORKER_ID,
        }
    )


def build_share_control_body(diagram_id: str, action: str, user_id: int = 0) -> str:
    """Kick or close envelope so every worker drops stale sockets."""
    return _stamp(
        {
            "action": action,
            "diagram_id": diagram_id,
            "from_tab": "-",
            "body": "-",
            "user_id": user_id,
        }
    )


def _worker(raw: object) -> str:
    if not isinstance(raw, str):
        return ""
    return raw


def _user_id(raw: object) -> int:
    if isinstance(raw, bool) or not isinstance(raw, int):
        return 0
    return raw


def parse_share_fanout_message(raw: str) -> Optional[ShareFanoutCommand]:
    """Return a command, or None when the envelope is unusable."""
    try:
        payload = json.loads(raw)
    except JSON_PARSE_ERRORS:
        return None
    if not isinstance(payload, dict):
        return None
    secret = _origin_secret()
    if secret and payload.get("origin") != secret:
        logger.warning("[DiagramShare] rejected fan-out envelope with invalid origin")
        return None
    diagram_id = payload.get("diagram_id")
    if not isinstance(diagram_id, str) or not diagram_id:
        return None
    action = payload.get("action") or "spec"
    if not isinstance(action, str) or action not in _ACTIONS:
        return None
    worker = _worker(payload.get("worker"))
    if action == "roster":
        body = payload.get("body")
        if not isinstance(body, str):
            return None
        return {
            "action": action,
            "diagram_id": diagram_id,
            "from_tab": "-",
            "body": body,
            "user_id": 0,
            "worker": worker,
        }
    if action == "kick":
        user_id = _user_id(payload.get("user_id"))
        if user_id <= 0:
            return None
        return {
            "action": action,
            "diagram_id": diagram_id,
            "from_tab": "-",
            "body": "-",
            "user_id": user_id,
            "worker": worker,
        }
    if action == "close":
        return {
            "action": action,
            "diagram_id": diagram_id,
            "from_tab": "-",
            "body": "-",
            "user_id": 0,
            "worker": worker,
        }
    from_tab = payload.get("from_tab")
    body = payload.get("body")
    if not isinstance(from_tab, str) or not from_tab:
        return None
    if not isinstance(body, str) or not body:
        return None
    return {
        "action": "spec",
        "diagram_id": diagram_id,
        "from_tab": from_tab,
        "body": body,
        "user_id": 0,
        "worker": worker,
    }


def parse_share_fanout_body(raw: str) -> Optional[tuple[str, str, str]]:
    """Return ``(diagram_id, from_tab, body)`` for a spec envelope."""
    message = parse_share_fanout_message(raw)
    if message is None or message["action"] != "spec":
        return None
    return message["diagram_id"], message["from_tab"], message["body"]


async def _publish(envelope: str, diagram_id: str) -> bool:
    """Publish one envelope. False when fan-out is off or Redis is unavailable."""
    if not is_ws_fanout_enabled():
        return False
    redis = get_async_redis()
    if redis is None:
        return False
    try:
        await redis.publish(SHARE_FANOUT_CHANNEL, envelope)
    except REDIS_ERRORS as exc:
        logger.warning("[DiagramShare] fan-out publish failed diagram=%s: %s", diagram_id, exc)
        return False
    return True


async def publish_share_spec(diagram_id: str, from_tab: str, body: str) -> None:
    """Deliver a spec snapshot on this worker, and to other workers when fan-out is on."""
    await relay_share_spec(diagram_id, from_tab, body)
    await _publish(build_share_fanout_body(diagram_id, from_tab, body), diagram_id)


async def publish_share_roster(diagram_id: str, tabs: list[ShareTab]) -> None:
    """Tell every open share stream who the editor is now."""
    push_roster(diagram_id, tabs)
    await _publish(build_share_roster_body(diagram_id, encode_tabs(tabs)), diagram_id)


async def publish_share_kick(diagram_id: str, user_id: int) -> None:
    """Close this user's sockets here, and tell other workers to do the same."""
    await close_share_sockets_for_user(diagram_id, user_id)
    await _publish(build_share_control_body(diagram_id, "kick", user_id), diagram_id)


async def publish_share_close(diagram_id: str) -> None:
    """Close every socket for a diagram that was deleted or whose queue was cleared."""
    await close_share_room(diagram_id)
    await _publish(build_share_control_body(diagram_id, "close"), diagram_id)
