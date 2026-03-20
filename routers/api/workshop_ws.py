"""
Workshop WebSocket Router
=========================

WebSocket endpoint for real-time collaborative diagram editing.

Features:
- Real-time diagram updates broadcast to all participants
- User presence tracking
- Conflict resolution (last-write-wins with timestamps)

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import json
import logging
import re
from typing import Any, Dict
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState

from services.features.ws_redis_fanout_config import is_ws_fanout_enabled
from services.features.ws_redis_fanout_publish import publish_workshop_fanout_async
from services.features.workshop_ws_connection_state import (
    ACTIVE_CONNECTIONS as active_connections,
    ACTIVE_EDITORS as active_editors,
)
from services.infrastructure.monitoring.ws_metrics import (
    record_ws_auth_failure,
    record_ws_rate_limit_hit,
    record_ws_workshop_connection_delta,
    redis_increment_active_total,
)
from services.workshop import workshop_service
from services.workshop.workshop_ws_editor_redis import (
    load_editors,
    remove_user_from_all_nodes,
    save_editors,
)

try:
    from services.redis.cache.redis_user_cache import user_cache as redis_user_cache
except ImportError:
    redis_user_cache = None

from utils.auth_ws import authenticate_websocket_user
from utils.ws_limits import (
    DEFAULT_MAX_WS_MESSAGES_PER_SECOND,
    DEFAULT_MAX_WS_TEXT_BYTES,
    WebsocketMessageRateLimiter,
    inbound_text_exceeds_limit,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# User colors for visual indicators (consistent per user)
USER_COLORS = [
    "#FF6B6B",  # Red
    "#4ECDC4",  # Teal
    "#45B7D1",  # Blue
    "#FFA07A",  # Light Salmon
    "#98D8C8",  # Mint
    "#F7DC6F",  # Yellow
    "#BB8FCE",  # Purple
    "#85C1E2",  # Sky Blue
]

USER_EMOJIS = ["✏️", "🖊️", "✒️", "🖋️", "📝", "✍️", "🖍️", "🖌️"]


@router.websocket("/ws/workshop/{code}")
async def workshop_websocket(
    websocket: WebSocket,
    code: str,
):
    """
    WebSocket endpoint for workshop collaboration.

    Messages:
    - Client -> Server:
      - {"type": "join", "diagram_id": "..."}
      - {"type": "update", "diagram_id": "...", "spec": {...}, "timestamp": "..."}
      - {"type": "node_editing", "node_id": "...", "editing": true/false}
      - {"type": "ping"}

    - Server -> Client:
      - {"type": "joined", "user_id": 123, "participants": [...]}
      - {"type": "update", "diagram_id": "...", "nodes": [...], "connections": [...],
         "user_id": 123, "timestamp": "..."}
      - {"type": "node_editing", "node_id": "...", "user_id": 123, "username": "...",
         "editing": true/false, "color": "...", "emoji": "..."}
      - {"type": "user_joined", "user_id": 123}
      - {"type": "user_left", "user_id": 123}
      - {"type": "error", "message": "..."}
      - {"type": "pong"}

    Args:
        websocket: WebSocket connection
        code: Workshop code
    """
    user, auth_error = authenticate_websocket_user(websocket)
    if auth_error or user is None:
        try:
            record_ws_auth_failure()
        except Exception:  # pylint: disable=broad-except
            pass
        reason = auth_error or "Authentication failed"
        await websocket.close(code=4001, reason=reason)
        logger.warning("[WorkshopWS] Auth failed: %s", reason)
        return

    logger.info("[WorkshopWS] connection accepted user_id=%s", user.id)

    # Normalize and validate code (digits and dash only, xxx-xxx format)
    code = code.strip()

    # Validate workshop code format
    if not re.match(r'^\d{3}-\d{3}$', code):
        await websocket.close(code=1008, reason="Invalid presentation code format")
        logger.warning("[WorkshopWS] Invalid presentation code format: %s", code)
        return

    # Verify workshop code and get diagram info
    workshop_info = await workshop_service.join_workshop(code, user.id)
    if not workshop_info:
        await websocket.close(code=1008, reason="Invalid presentation code")
        return

    diagram_id = workshop_info["diagram_id"]

    # Accept connection only after authentication and validation
    await websocket.accept()

    rate_limiter = WebsocketMessageRateLimiter(
        DEFAULT_MAX_WS_MESSAGES_PER_SECOND,
    )

    # Add to active connections
    if code not in active_connections:
        active_connections[code] = {}
    active_connections[code][user.id] = websocket

    # Initialize active editors tracking for this workshop
    if code not in active_editors:
        active_editors[code] = {}

    try:
        record_ws_workshop_connection_delta(1)
        redis_increment_active_total(1)
    except Exception:  # pylint: disable=broad-except
        pass

    logger.info(
        "[WorkshopWS] User %s connected to workshop %s (diagram %s)",
        user.id,
        code,
        diagram_id,
    )

    # Get current participants
    participant_ids = await workshop_service.get_participants(code)
    username = getattr(user, "username", None) or f"User {user.id}"

    # Get usernames for participants (from cache or database)
    participants_with_names = []
    for pid in participant_ids:
        if redis_user_cache:
            participant_user = redis_user_cache.get_by_id(pid)
            if participant_user:
                p_username = getattr(participant_user, "username", None) or f"User {pid}"
                participants_with_names.append({
                    "user_id": pid,
                    "username": p_username,
                })
            else:
                participants_with_names.append({
                    "user_id": pid,
                    "username": f"User {pid}",
                })
        else:
            participants_with_names.append({
                "user_id": pid,
                "username": f"User {pid}",
            })

    # Notify user of successful join
    await websocket.send_json({
        "type": "joined",
        "user_id": user.id,
        "username": username,
        "diagram_id": diagram_id,
        "participants": participant_ids,  # Keep for backward compatibility
        "participants_with_names": participants_with_names,  # New: includes usernames
    })

    # Send current active editors for all nodes (Redis when multi-worker fan-out)
    _editor_map = (
        load_editors(code)
        if is_ws_fanout_enabled()
        else active_editors.get(code, {})
    )
    for node_id, editors in _editor_map.items():
        for editor_user_id, editor_username in editors.items():
            if editor_user_id != user.id:
                color = USER_COLORS[editor_user_id % len(USER_COLORS)]
                emoji = USER_EMOJIS[editor_user_id % len(USER_EMOJIS)]
                await websocket.send_json({
                    "type": "node_editing",
                    "node_id": node_id,
                    "user_id": editor_user_id,
                    "username": editor_username,
                    "editing": True,
                    "color": color,
                    "emoji": emoji,
                })

    # Notify other participants
    await broadcast_to_others(
        code,
        user.id,
        {
            "type": "user_joined",
            "user_id": user.id,
            "username": username,
        },
    )

    try:
        while True:
            # Receive message
            data = await websocket.receive_text()
            if inbound_text_exceeds_limit(data, DEFAULT_MAX_WS_TEXT_BYTES):
                await websocket.send_json({
                    "type": "error",
                    "message": "Message too large",
                })
                continue
            if not rate_limiter.allow():
                try:
                    record_ws_rate_limit_hit()
                except Exception:  # pylint: disable=broad-except
                    pass
                await websocket.send_json({
                    "type": "error",
                    "message": "Rate limit exceeded",
                })
                continue

            try:
                message = json.loads(data)
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON",
                })
                continue

            msg_type = message.get("type")

            if msg_type == "ping":
                # Respond to ping
                await websocket.send_json({"type": "pong"})
                continue

            if msg_type == "join":
                # Already joined, just acknowledge
                participant_ids = await workshop_service.get_participants(code)
                current_username = getattr(user, "username", None) or f"User {user.id}"
                participants_with_names = []
                for pid in participant_ids:
                    if redis_user_cache:
                        participant_user = redis_user_cache.get_by_id(pid)
                        if participant_user:
                            p_username = getattr(participant_user, "username", None) or f"User {pid}"
                            participants_with_names.append({
                                "user_id": pid,
                                "username": p_username,
                            })
                        else:
                            participants_with_names.append({
                                "user_id": pid,
                                "username": f"User {pid}",
                            })
                    else:
                        participants_with_names.append({
                            "user_id": pid,
                            "username": f"User {pid}",
                        })

                await websocket.send_json({
                    "type": "joined",
                    "user_id": user.id,
                    "username": current_username,
                    "diagram_id": diagram_id,
                    "participants": participant_ids,  # Keep for backward compatibility
                    "participants_with_names": participants_with_names,  # New: includes usernames
                })
                continue

            if msg_type == "node_editing":
                # Track when user starts/stops editing a node
                node_id = message.get("node_id")
                editing = message.get("editing", False)
                username = getattr(user, "username", None) or f"User {user.id}"

                # Validate node_id
                if not node_id or not isinstance(node_id, str) or len(node_id) > 200:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Invalid node_id",
                    })
                    continue

                if not node_id:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Missing node_id in node_editing",
                    })
                    continue

                if code not in active_editors:
                    active_editors[code] = {}

                if node_id not in active_editors[code]:
                    active_editors[code][node_id] = {}

                if editing:
                    # User started editing
                    active_editors[code][node_id][user.id] = username
                    color = USER_COLORS[user.id % len(USER_COLORS)]
                    emoji = USER_EMOJIS[user.id % len(USER_EMOJIS)]
                else:
                    # User stopped editing
                    active_editors[code][node_id].pop(user.id, None)
                    if not active_editors[code][node_id]:
                        del active_editors[code][node_id]
                    color = None
                    emoji = None

                if is_ws_fanout_enabled():
                    save_editors(code, active_editors[code])

                # Broadcast to all participants
                await broadcast_to_all(
                    code,
                    {
                        "type": "node_editing",
                        "node_id": node_id,
                        "user_id": user.id,
                        "username": username,
                        "editing": editing,
                        "color": color,
                        "emoji": emoji,
                    },
                )
                continue

            if msg_type == "update":
                # Validate update message
                if message.get("diagram_id") != diagram_id:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Diagram ID mismatch",
                    })
                    continue

                # Support both full spec (backward compatibility) and granular updates
                spec = message.get("spec")
                nodes = message.get("nodes")  # Granular: only changed nodes
                connections = message.get("connections")  # Granular: only changed connections

                if not spec and not nodes and not connections:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Missing spec, nodes, or connections in update",
                    })
                    continue

                # Validate nodes array if provided
                if nodes is not None:
                    if not isinstance(nodes, list):
                        await websocket.send_json({
                            "type": "error",
                            "message": "Invalid nodes format (must be array)",
                        })
                        continue
                    # Limit update size to prevent DoS
                    if len(nodes) > 100:
                        await websocket.send_json({
                            "type": "error",
                            "message": "Too many nodes in update (max 100)",
                        })
                        continue

                # Validate connections array if provided
                if connections is not None:
                    if not isinstance(connections, list):
                        await websocket.send_json({
                            "type": "error",
                            "message": "Invalid connections format (must be array)",
                        })
                        continue
                    # Limit update size to prevent DoS
                    if len(connections) > 200:
                        await websocket.send_json({
                            "type": "error",
                            "message": "Too many connections in update (max 200)",
                        })
                        continue

                # Refresh participant TTL on activity
                await workshop_service.refresh_participant_ttl(code, user.id)

                # Broadcast granular update (preferred) or full spec (fallback)
                update_message = {
                    "type": "update",
                    "diagram_id": diagram_id,
                    "user_id": user.id,
                    "timestamp": message.get("timestamp") or datetime.utcnow().isoformat(),
                }

                if nodes is not None or connections is not None:
                    # Granular update
                    if nodes is not None:
                        update_message["nodes"] = nodes
                    if connections is not None:
                        update_message["connections"] = connections
                else:
                    # Full spec (backward compatibility)
                    update_message["spec"] = spec

                await broadcast_to_others(
                    code,
                    user.id,
                    update_message,
                )

                logger.debug(
                    "[WorkshopWS] User %s updated diagram %s in workshop %s (granular: %s)",
                    user.id,
                    diagram_id,
                    code,
                    nodes is not None or connections is not None,
                )
                continue

            # Unknown message type
            await websocket.send_json({
                "type": "error",
                "message": f"Unknown message type: {msg_type}",
            })

    except WebSocketDisconnect:
        logger.info(
            "[WorkshopWS] User %s disconnected from workshop %s",
            user.id,
            code,
        )
    except Exception as e:
        logger.error(
            "[WorkshopWS] Error in workshop WebSocket: %s",
            e,
            exc_info=True,
        )
        # Try to send error message to client before closing
        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Presentation mode error: {str(e)}",
                })
        except Exception:
            pass  # Ignore errors when sending error message
    finally:
        try:
            record_ws_workshop_connection_delta(-1)
            redis_increment_active_total(-1)
        except Exception:  # pylint: disable=broad-except
            pass

        um_leave = getattr(user, "username", None) or f"User {user.id}"

        if is_ws_fanout_enabled():
            editors_map = load_editors(code)
            nodes_with_user = [
                nid for nid, ed in editors_map.items()
                if user.id in ed
            ]
            remove_user_from_all_nodes(code, user.id, editors_map)
            for nid in nodes_with_user:
                await broadcast_to_others(
                    code,
                    user.id,
                    {
                        "type": "node_editing",
                        "node_id": nid,
                        "user_id": user.id,
                        "username": um_leave,
                        "editing": False,
                        "color": None,
                        "emoji": None,
                    },
                )
            if code in active_editors:
                for nid in list(active_editors[code].keys()):
                    ed = active_editors[code].get(nid)
                    if ed and user.id in ed:
                        ed.pop(user.id, None)
                        if not ed:
                            del active_editors[code][nid]
                if not active_editors[code]:
                    del active_editors[code]
        else:
            if code in active_editors:
                nodes_to_remove = []
                for node_id, editors in active_editors[code].items():
                    if user.id in editors:
                        editors.pop(user.id, None)
                        await broadcast_to_others(
                            code,
                            user.id,
                            {
                                "type": "node_editing",
                                "node_id": node_id,
                                "user_id": user.id,
                                "username": um_leave,
                                "editing": False,
                                "color": None,
                                "emoji": None,
                            },
                        )
                        if not editors:
                            nodes_to_remove.append(node_id)
                for node_id in nodes_to_remove:
                    del active_editors[code][node_id]
                if not active_editors[code]:
                    del active_editors[code]

        if code in active_connections:
            active_connections[code].pop(user.id, None)
            if not active_connections[code]:
                del active_connections[code]

        await workshop_service.remove_participant(code, user.id)

        await broadcast_to_others(
            code,
            user.id,
            {
                "type": "user_left",
                "user_id": user.id,
            },
        )


async def broadcast_to_others(
    code: str, sender_id: int, message: Dict[str, Any]
) -> None:
    """
    Broadcast message to all participants except sender.

    Args:
        code: Workshop code
        sender_id: User ID of sender (excluded from broadcast)
        message: Message to broadcast
    """
    if is_ws_fanout_enabled():
        try:
            data_str = json.dumps(message, ensure_ascii=False)
        except (TypeError, ValueError):
            logger.warning("[WorkshopWS] broadcast_to_others: serialize failed")
            return
        await publish_workshop_fanout_async({
            "v": 1, "k": "ws", "code": code, "mode": "others",
            "ex": sender_id, "d": data_str,
        })
        return

    if code not in active_connections:
        return

    disconnected = []
    for user_id, websocket in active_connections[code].items():
        if user_id == sender_id:
            continue

        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.send_json(message)
            else:
                disconnected.append(user_id)
        except Exception as e:
            logger.warning(
                "[WorkshopWS] Error broadcasting to user %s: %s",
                user_id,
                e,
            )
            disconnected.append(user_id)

    # Clean up disconnected connections
    for user_id in disconnected:
        active_connections[code].pop(user_id, None)
        await workshop_service.remove_participant(code, user_id)


async def broadcast_to_all(code: str, message: Dict[str, Any]) -> None:
    """
    Broadcast message to all participants.

    Args:
        code: Workshop code
        message: Message to broadcast
    """
    if is_ws_fanout_enabled():
        try:
            data_str = json.dumps(message, ensure_ascii=False)
        except (TypeError, ValueError):
            logger.warning("[WorkshopWS] broadcast_to_all: serialize failed")
            return
        await publish_workshop_fanout_async({
            "v": 1, "k": "ws", "code": code, "mode": "all",
            "ex": None, "d": data_str,
        })
        return

    if code not in active_connections:
        return

    disconnected = []
    for user_id, websocket in active_connections[code].items():
        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.send_json(message)
            else:
                disconnected.append(user_id)
        except Exception as e:
            logger.warning(
                "[WorkshopWS] Error broadcasting to user %s: %s",
                user_id,
                e,
            )
            disconnected.append(user_id)

    # Clean up disconnected connections
    for user_id in disconnected:
        active_connections[code].pop(user_id, None)
        await workshop_service.remove_participant(code, user_id)
