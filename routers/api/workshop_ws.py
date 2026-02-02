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
from typing import Dict, Set, Any, Optional
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends
from fastapi.websockets import WebSocketState

from models.domain.auth import User
from services.workshop import workshop_service
from utils.auth import decode_access_token

try:
    from services.redis.session.redis_session_manager import (
        get_session_manager as redis_get_session_manager
    )
except ImportError:
    redis_get_session_manager = None

try:
    from services.redis.cache.redis_user_cache import user_cache as redis_user_cache
except ImportError:
    redis_user_cache = None

logger = logging.getLogger(__name__)

router = APIRouter()

# Track active WebSocket connections by workshop code
# Structure: {workshop_code: {user_id: websocket}}
active_connections: Dict[str, Dict[int, WebSocket]] = {}

# Track active editors per node: {workshop_code: {node_id: {user_id: username}}}
active_editors: Dict[str, Dict[str, Dict[int, str]]] = {}

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
      - {"type": "update", "diagram_id": "...", "nodes": [...], "connections": [...], "user_id": 123, "timestamp": "..."}
      - {"type": "node_editing", "node_id": "...", "user_id": 123, "username": "...", "editing": true/false, "color": "...", "emoji": "..."}
      - {"type": "user_joined", "user_id": 123}
      - {"type": "user_left", "user_id": 123}
      - {"type": "error", "message": "..."}
      - {"type": "pong"}

    Args:
        websocket: WebSocket connection
        code: Workshop code
    """
    # Authenticate user from WebSocket BEFORE accepting (security best practice)
    user = None
    try:
        # Get token from query params or cookies
        token = websocket.query_params.get('token')
        if not token:
            token = websocket.cookies.get('access_token')

        if not token:
            await websocket.close(code=4001, reason="No authentication token")
            logger.warning("[WorkshopWS] Auth failed: No token provided")
            return

        # Decode and validate token
        payload = decode_access_token(token)
        user_id_str = payload.get("sub")

        if not user_id_str:
            await websocket.close(code=4001, reason="Invalid token payload")
            logger.warning("[WorkshopWS] Auth failed: Invalid token payload")
            return

        # Session validation: Check if session exists in Redis
        if redis_get_session_manager:
            session_manager = redis_get_session_manager()
            if session_manager and not session_manager.is_session_valid(
                int(user_id_str), token
            ):
                await websocket.close(
                    code=4001, reason="Session expired or invalidated"
                )
                logger.warning(
                    "[WorkshopWS] Auth failed: Session invalid for user %s",
                    user_id_str,
                )
                return

        # Get user from cache (with database fallback)
        if redis_user_cache:
            user = redis_user_cache.get_by_id(int(user_id_str))

        if not user:
            await websocket.close(code=4001, reason="User not found")
            logger.warning(
                "[WorkshopWS] Auth failed: User %s not found", user_id_str
            )
            return

        logger.debug("[WorkshopWS] Authenticated: user %d", user.id)

    except Exception as e:
        logger.error("[WorkshopWS] Auth error: %s", e, exc_info=True)
        await websocket.close(code=4001, reason=f"Authentication failed: {str(e)}")
        return

    # Normalize and validate code (digits and dash only, xxx-xxx format)
    code = code.strip()
    
    # Validate workshop code format
    import re
    if not re.match(r'^\d{3}-\d{3}$', code):
        await websocket.close(code=1008, reason="Invalid workshop code format")
        logger.warning("[WorkshopWS] Invalid workshop code format: %s", code)
        return

    # Verify workshop code and get diagram info
    workshop_info = await workshop_service.join_workshop(code, user.id)
    if not workshop_info:
        await websocket.close(code=1008, reason="Invalid workshop code")
        return

    diagram_id = workshop_info["diagram_id"]

    # Accept connection only after authentication and validation
    await websocket.accept()

    # Add to active connections
    if code not in active_connections:
        active_connections[code] = {}
    active_connections[code][user.id] = websocket

    # Initialize active editors tracking for this workshop
    if code not in active_editors:
        active_editors[code] = {}

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

    # Send current active editors for all nodes
    if code in active_editors:
        for node_id, editors in active_editors[code].items():
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
                    "message": f"Workshop error: {str(e)}",
                })
        except Exception:
            pass  # Ignore errors when sending error message
    finally:
        # Remove user from all active editors
        if code in active_editors:
            nodes_to_remove = []
            for node_id, editors in active_editors[code].items():
                if user.id in editors:
                    editors.pop(user.id, None)
                    # Notify others that user stopped editing
                    await broadcast_to_others(
                        code,
                        user.id,
                        {
                            "type": "node_editing",
                            "node_id": node_id,
                            "user_id": user.id,
                            "username": editors.get(user.id, f"User {user.id}"),
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

        # Remove from active connections
        if code in active_connections:
            active_connections[code].pop(user.id, None)
            if not active_connections[code]:
                del active_connections[code]

        # Remove from participants
        await workshop_service.remove_participant(code, user.id)

        # Notify other participants
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
