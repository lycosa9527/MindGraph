"""
MindMate collab WebSocket endpoint.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import json
import logging
import os

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from config.settings import config
from models.domain.auth import User
from services.features.mindmate_collab.config import MINDMATE_COLLAB_MAX_CHAT_CONTENT_CHARS
from services.features.mindmate_collab.dify_stream_control import acquire_dify_stream_lock
from services.features.mindmate_collab.dify_stream import schedule_assistant_reply
from services.features.mindmate_collab.manager_access import get_mindmate_collab_manager
from services.features.mindmate_collab.mention import extract_mindmate_query, message_mentions_mindmate
from services.features.mindmate_collab.redis_keys import normalize_collab_code
from services.features.mindmate_collab.resume_tokens import (
    join_resume_claims_match_user_room,
    mint_join_resume_token_async,
    peek_join_resume_claims_async,
    try_consume_join_resume_token_async,
)
from services.features.mindmate_collab.ws_broadcast import broadcast_to_others
from services.features.mindmate_collab.ws_registry import (
    MindmateCollabWsHandle,
    close_superseded_connection,
    register_connection,
    shutdown_connection_handle,
    unregister_connection,
)
from services.online_collab.participant.online_collab_ws_rate_limit import (
    check_canvas_collab_join_rate_limits,
)
from utils.auth_ws import authenticate_websocket_user
from utils.auth.school_tier import TIER_FEATURE_ONLINE_COLLAB, user_has_school_tier_feature
from utils.collab_ws_origin import close_ws_if_origin_disallowed
from utils.db.session_open import actor_rls_session
from utils.ws_context import ws_managed_session
from utils.ws_limits import (
    DEFAULT_MAX_WS_MESSAGES_PER_SECOND,
    DEFAULT_MAX_WS_TEXT_BYTES,
    MAX_COLLAB_INBOUND_JSON_DEPTH,
    WebsocketMessageRateLimiter,
    collab_json_exceeds_depth,
    inbound_text_exceeds_limit,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _parse_positive_int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        parsed = int(raw)
    except ValueError:
        return default
    return parsed if parsed > 0 else default


_COLLAB_WS_MAX_PER_USER_ENDPOINT = _parse_positive_int_env("COLLAB_WS_MAX_PER_USER_ENDPOINT", 5)
_COLLAB_WS_MAX_PER_USER_GLOBAL = _parse_positive_int_env("COLLAB_WS_MAX_PER_USER_GLOBAL", 20)


async def _writer_loop(handle: MindmateCollabWsHandle) -> None:
    while True:
        kind, payload = await handle.send_queue.get()
        if kind == "stop":
            break
        if kind == "text":
            await handle.websocket.send_text(payload)


def _resume_token_from_websocket(websocket: WebSocket) -> str:
    for proto in websocket.scope.get("subprotocols") or []:
        if isinstance(proto, str) and proto.startswith("mg-resume."):
            token = proto[len("mg-resume.") :].strip()
            if token:
                return token
    return (websocket.query_params.get("resume") or websocket.query_params.get("resume_token") or "").strip()


async def _tier_allowed(user: User) -> bool:
    async with actor_rls_session(user) as db:
        return await user_has_school_tier_feature(db, user, TIER_FEATURE_ONLINE_COLLAB)


async def _handle_ping(websocket: WebSocket, code: str, user_id: int) -> None:
    mgr = get_mindmate_collab_manager()
    await mgr.refresh_participant_ttl(code, user_id)
    await mgr.touch_activity(code)
    await websocket.send_json({"type": "pong"})


@router.websocket("/ws/mindmate-collab/{code}")
async def mindmate_collab_websocket(websocket: WebSocket, code: str) -> None:
    """MindMate shared chatroom WebSocket — join, chat, Dify stream fan-out."""
    if not config.FEATURE_MINDMATE_COLLAB:
        try:
            await websocket.close(code=1008, reason="Feature disabled")
        except (RuntimeError, OSError):
            pass
        return

    if await close_ws_if_origin_disallowed(websocket, "MindmateCollab"):
        return

    user, auth_err = await authenticate_websocket_user(websocket)
    if auth_err or not user:
        try:
            await websocket.close(code=1008, reason=auth_err or "Unauthorized")
        except (RuntimeError, OSError):
            pass
        return

    if not await _tier_allowed(user):
        try:
            await websocket.close(code=1008, reason="Feature unavailable")
        except (RuntimeError, OSError):
            pass
        return

    norm_code = normalize_collab_code(code)
    mgr = get_mindmate_collab_manager()
    session = await mgr.load_session_by_code(norm_code)
    if not session:
        try:
            await websocket.close(code=1008, reason="Invalid room")
        except (RuntimeError, OSError):
            pass
        return

    if await mgr.session_is_closing(norm_code):
        try:
            await websocket.close(code=1008, reason="Room closing")
        except (RuntimeError, OSError):
            pass
        return

    if not await mgr.user_may_connect(int(user.id), session):
        try:
            await websocket.close(code=1008, reason="Access denied")
        except (RuntimeError, OSError):
            pass
        return

    resume_raw = _resume_token_from_websocket(websocket)
    has_resume = False
    if resume_raw:
        claims = await peek_join_resume_claims_async(resume_raw)
        has_resume = bool(
            claims and join_resume_claims_match_user_room(int(user.id), norm_code, claims),
        )

    if not has_resume:
        rate_msg = await check_canvas_collab_join_rate_limits(int(user.id), websocket)
        if rate_msg:
            try:
                await websocket.close(code=1008, reason="Rate limited")
            except (RuntimeError, OSError):
                pass
            return

    subprotocol = f"mg-resume.{resume_raw}" if resume_raw and has_resume else None
    if subprotocol:
        await websocket.accept(subprotocol=subprotocol)
    else:
        await websocket.accept()

    if resume_raw and has_resume:
        await try_consume_join_resume_token_async(resume_raw)

    handle = MindmateCollabWsHandle(websocket)
    handle.writer_task = asyncio.create_task(_writer_loop(handle), name="mindmate-collab-writer")
    previous = register_connection(norm_code, int(user.id), handle)
    if previous is not None:
        await close_superseded_connection(previous)

    if not await mgr.add_participant(norm_code, int(user.id)):
        unregister_connection(norm_code, int(user.id))
        await shutdown_connection_handle(handle)
        try:
            await websocket.close(code=1008, reason="Room full")
        except (RuntimeError, OSError):
            pass
        return

    rate_limiter = WebsocketMessageRateLimiter(DEFAULT_MAX_WS_MESSAGES_PER_SECOND)

    async with ws_managed_session(
        websocket,
        user_id=int(user.id),
        endpoint="mindmate_collab",
        max_per_user_endpoint=_COLLAB_WS_MAX_PER_USER_ENDPOINT,
        max_per_user_global=_COLLAB_WS_MAX_PER_USER_GLOBAL,
    ):
        history = await mgr.fetch_message_history(session.id)
        participants = await mgr.participant_count(norm_code)
        resume_token = await mint_join_resume_token_async(int(user.id), norm_code, session.id)

        joined_payload = {
            "type": "joined",
            "user_id": int(user.id),
            "owner_id": session.owner_user_id,
            "session_id": session.id,
            "code": session.code,
            "title": session.title,
            "visibility": session.visibility,
            "participants": participants,
            "resume_token": resume_token,
        }
        await websocket.send_json(joined_payload)
        await websocket.send_json({"type": "snapshot", "messages": history})

        await broadcast_to_others(
            norm_code,
            int(user.id),
            {
                "type": "user_joined",
                "user_id": int(user.id),
                "username": getattr(user, "username", None) or getattr(user, "name", None),
            },
        )

        try:
            while True:
                raw = await websocket.receive_text()
                if inbound_text_exceeds_limit(raw, DEFAULT_MAX_WS_TEXT_BYTES):
                    await websocket.send_json(
                        {"type": "error", "code": "message_too_large", "message": "Message too large"},
                    )
                    continue
                if not rate_limiter.allow():
                    await websocket.send_json(
                        {"type": "error", "code": "rate_limit", "message": "Too many messages"},
                    )
                    continue
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if not isinstance(msg, dict):
                    continue
                if collab_json_exceeds_depth(msg, MAX_COLLAB_INBOUND_JSON_DEPTH):
                    await websocket.send_json(
                        {"type": "error", "code": "invalid_payload", "message": "Invalid payload"},
                    )
                    continue
                msg_type = msg.get("type")
                if msg_type == "ping":
                    await _handle_ping(websocket, norm_code, int(user.id))
                    continue
                if msg_type != "chat":
                    continue
                content = str(msg.get("content") or "").strip()
                if not content:
                    continue
                if len(content) > MINDMATE_COLLAB_MAX_CHAT_CONTENT_CHARS:
                    await websocket.send_json(
                        {
                            "type": "error",
                            "code": "content_too_long",
                            "message": "Message too long",
                        },
                    )
                    continue

                to_mindmate = bool(msg.get("to_mindmate"))
                agent_aliases: tuple[str, ...] = ()
                agent_name = getattr(user, "mindmate_agent_name", None)
                if agent_name:
                    agent_aliases = (str(agent_name),)
                if not to_mindmate:
                    to_mindmate = message_mentions_mindmate(content, agent_aliases)

                await mgr.refresh_participant_ttl(norm_code, int(user.id))
                await mgr.touch_activity(norm_code)
                await mgr.persist_message(
                    session.id,
                    role="user",
                    content=content,
                    sender_user_id=int(user.id),
                )
                user_frame = {
                    "type": "user_message",
                    "content": content,
                    "sender_user_id": int(user.id),
                    "username": getattr(user, "username", None) or getattr(user, "name", None),
                    "to_mindmate": to_mindmate,
                }
                await broadcast_to_others(norm_code, int(user.id), user_frame)

                if not to_mindmate:
                    continue

                if not await acquire_dify_stream_lock(norm_code):
                    await websocket.send_json(
                        {
                            "type": "error",
                            "code": "mindmate_responding",
                            "message": "MindMate is responding",
                        },
                    )
                    continue

                dify_query = extract_mindmate_query(content, agent_aliases)
                conv_id = session.dify_conversation_id
                schedule_assistant_reply(
                    code=norm_code,
                    session_id=session.id,
                    org_id=session.organization_id,
                    user_message=dify_query,
                    sender_user_id=int(user.id),
                    conversation_id=conv_id,
                )
        except WebSocketDisconnect:
            pass
        finally:
            await shutdown_connection_handle(handle)
            unregister_connection(norm_code, int(user.id))
            await mgr.remove_participant(norm_code, int(user.id))
            await broadcast_to_others(
                norm_code,
                int(user.id),
                {"type": "user_left", "user_id": int(user.id)},
            )
