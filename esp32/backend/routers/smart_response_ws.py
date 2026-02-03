"""
Smart Response WebSocket Router
Handles WebSocket connections for ESP32 watches and teacher sessions
"""

import asyncio
import base64
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from models.domain.auth import User
from routers.core.dependencies import get_current_user, get_db
from services.features.dashscope_stt import get_stt_service

router = APIRouter()

logger = logging.getLogger(__name__)

# Track watch connections
watch_connections: Dict[str, WebSocket] = {}

# Track teacher sessions
teacher_sessions: Dict[str, Dict] = {}

# Track STT sessions per watch
watch_stt_sessions: Dict[str, str] = {}


@router.websocket("/ws/watch/{watch_id}")
async def watch_websocket(
    websocket: WebSocket,
    watch_id: str,
    db: Session = Depends(get_db),
):
    """WebSocket endpoint for watch connections"""
    await websocket.accept()
    logger.info("Watch %s connected", watch_id)

    watch_connections[watch_id] = websocket

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            msg_type = message.get("type")

            if msg_type == "watch_connect":
                token = message.get("token", "")
                # TODO: Authenticate watch with token
                # For now, just accept
                await websocket.send_json({
                    "type": "watch_authenticated",
                    "status": "success",
                    "watch_id": watch_id,
                })

            elif msg_type == "audio":
                await handle_watch_audio(websocket, watch_id, message)

            elif msg_type == "learning_mode_ready":
                session_id = message.get("session_id")
                await notify_teacher_watch_ready(session_id, watch_id)

            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        logger.info("Watch %s disconnected", watch_id)
        watch_connections.pop(watch_id, None)
        if watch_id in watch_stt_sessions:
            stt_service = get_stt_service()
            await stt_service.close_session(watch_stt_sessions[watch_id])
            del watch_stt_sessions[watch_id]


@router.websocket("/ws/smart-response/{session_id}")
async def teacher_smart_response_ws(
    websocket: WebSocket,
    session_id: str,
    current_user: User = Depends(get_current_user),
):
    """WebSocket endpoint for teacher Smart Response sessions"""
    await websocket.accept()
    logger.info("Teacher %s connected to session %s", current_user.id, session_id)

    teacher_sessions[session_id] = {
        "teacher_ws": websocket,
        "diagram_id": None,
        "watch_ids": [],
        "created_at": datetime.utcnow(),
        "user_id": current_user.id,
    }

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            msg_type = message.get("type")

            if msg_type == "start_learning_mode":
                diagram_id = message.get("diagram_id")
                watch_ids = message.get("watch_ids", [])
                await broadcast_learning_mode(session_id, diagram_id, watch_ids)

            elif msg_type == "stop_learning_mode":
                await broadcast_stop_learning_mode(session_id)

            elif msg_type == "fill_request_response":
                await handle_fill_request_response(session_id, message)

    except WebSocketDisconnect:
        logger.info("Teacher disconnected from session %s", session_id)
        teacher_sessions.pop(session_id, None)


async def handle_watch_audio(websocket: WebSocket, watch_id: str, message: dict):
    """Handle audio data from watch"""
    audio_data_b64 = message.get("data", "")
    session_id = message.get("session_id")

    if not audio_data_b64:
        return

    try:
        audio_data = base64.b64decode(audio_data_b64)

        stt_service = get_stt_service()
        if not stt_service.is_available():
            logger.warning("STT service not available")
            return

        stt_session_id = watch_stt_sessions.get(watch_id)
        if not stt_session_id:
            stt_session_id = f"watch_{watch_id}_{session_id}"
            await stt_service.create_recognition_session(
                stt_session_id,
                on_transcription=lambda text, is_final: asyncio.create_task(
                    handle_transcription(websocket, watch_id, session_id, text, is_final)
                ),
            )
            watch_stt_sessions[watch_id] = stt_session_id

        await stt_service.send_audio_frame(stt_session_id, audio_data)

    except Exception as e:
        logger.error("Error processing watch audio: %s", e, exc_info=True)


async def handle_transcription(
    websocket: WebSocket,
    watch_id: str,
    session_id: str,
    text: str,
    is_final: bool,
):
    """Handle transcription result from STT"""
    await websocket.send_json({
        "type": "transcription",
        "session_id": session_id,
        "watch_id": watch_id,
        "text": text,
        "is_final": is_final,
    })

    if is_final:
        await notify_teacher_transcription(session_id, watch_id, text)


async def broadcast_learning_mode(
    session_id: str,
    diagram_id: str,
    watch_ids: List[str],
):
    """Broadcast learning mode command to watches"""
    if session_id not in teacher_sessions:
        logger.warning("Session %s not found", session_id)
        return

    session = teacher_sessions[session_id]
    session["diagram_id"] = diagram_id
    session["watch_ids"] = watch_ids if watch_ids else list(watch_connections.keys())

    target_watches = session["watch_ids"]

    for watch_id in target_watches:
        if watch_id in watch_connections:
            ws = watch_connections[watch_id]
            await ws.send_json({
                "type": "enter_learning_mode",
                "session_id": session_id,
                "diagram_id": diagram_id,
            })

    await session["teacher_ws"].send_json({
        "type": "learning_mode_started",
        "session_id": session_id,
        "watches_ready": target_watches,
        "total_watches": len(target_watches),
    })


async def broadcast_stop_learning_mode(session_id: str):
    """Broadcast stop learning mode command to watches"""
    if session_id not in teacher_sessions:
        return

    session = teacher_sessions[session_id]
    watch_ids = session.get("watch_ids", [])

    for watch_id in watch_ids:
        if watch_id in watch_connections:
            ws = watch_connections[watch_id]
            await ws.send_json({
                "type": "stop_learning_mode",
                "session_id": session_id,
            })


async def notify_teacher_watch_ready(session_id: str, watch_id: str):
    """Notify teacher that a watch is ready"""
    if session_id not in teacher_sessions:
        return

    session = teacher_sessions[session_id]
    await session["teacher_ws"].send_json({
        "type": "watch_ready",
        "session_id": session_id,
        "watch_id": watch_id,
    })


async def notify_teacher_transcription(
    session_id: str,
    watch_id: str,
    text: str,
):
    """Notify teacher of transcription"""
    if session_id not in teacher_sessions:
        return

    session = teacher_sessions[session_id]
    await session["teacher_ws"].send_json({
        "type": "transcription_notification",
        "session_id": session_id,
        "watch_id": watch_id,
        "text": text,
    })


async def handle_fill_request_response(session_id: str, message: dict):
    """Handle teacher's response to fill request"""
    watch_id = message.get("watch_id")
    node_id = message.get("node_id")
    action = message.get("action")

    if watch_id in watch_connections:
        ws = watch_connections[watch_id]
        await ws.send_json({
            "type": "fill_request_result",
            "session_id": session_id,
            "node_id": node_id,
            "status": action,
            "message": "Request processed",
        })