"""
Text-only conversational replies for one-sentence panel (no Omni realtime).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import WebSocket

from services.kitty.ack.ack_emit import emit_user_ack
from services.kitty.context.messaging import resolve_voice_interaction_language, safe_websocket_send
from services.kitty.infra.desktop.kitty_voice_phase_fanout import (
    fanout_voice_phase_from_outbound_type,
)
from services.kitty.session.memory import get_session_memory
from services.kitty.session.runtime_state import voice_sessions
from services.llm import llm_service
from services.utils.error_types import LLM_PIPELINE_ERRORS
from utils.prompt_locale import output_language_instruction

logger = logging.getLogger(__name__)


def _is_text_only_one_sentence(voice_session_id: str) -> bool:
    session = voice_sessions.get(voice_session_id) or {}
    if str(session.get("_kitty_client_mode") or "") != "text":
        return False
    return str(session.get("active_panel") or "") == "one_sentence"


def _extract_reply_text(result: Any) -> str:
    if isinstance(result, dict):
        for key in ("content", "text", "response"):
            value = result.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    if isinstance(result, str) and result.strip():
        return result.strip()
    return ""


async def reply_text_only_conversational(
    websocket: WebSocket,
    voice_session_id: str,
    user_text: str,
    session_context: Dict[str, Any],
) -> bool:
    """
    Answer a non-command chat turn for text-only one-sentence sessions.

    Returns True when a reply was sent; False when this handler does not apply.
    """
    if not _is_text_only_one_sentence(voice_session_id):
        return False

    text = str(user_text or "").strip()
    if not text:
        return False

    lang = resolve_voice_interaction_language(session_context)
    lang_code = "en" if lang == "en" else "zh"
    diagram_type = str(
        voice_sessions.get(voice_session_id, {}).get("diagram_type") or session_context.get("diagram_type") or "mindmap"
    )
    memory = get_session_memory(voice_session_id)
    recent = memory.summarize_for_parser(5)

    if lang_code == "en":
        system = (
            "You are Kitty, a concise diagram editing assistant in the one-sentence panel. "
            "The user is refining a diagram. If they ask how to edit, suggest concrete "
            "commands like adding a branch, renaming the topic, or deleting a node. "
            "Keep replies under 80 words." + output_language_instruction("en")
        )
    else:
        system = (
            "你是 Kitty，一句话生成面板里的导图编辑助手。"
            "用户在修改导图。若用户在闲聊或询问怎么改，请用简短中文给出可执行建议，"
            "例如添加分支、改主题、删除节点。回复控制在 80 字以内。" + output_language_instruction("zh")
        )

    user_prompt = f"Diagram type: {diagram_type}\nRecent turns:\n{recent or '(none)'}\nUser: {text}"

    session = voice_sessions.get(voice_session_id) or {}
    user_raw = session.get("user_id")
    try:
        user_id = int(user_raw) if user_raw is not None else None
    except (TypeError, ValueError):
        user_id = None

    try:
        result = await llm_service.chat(
            prompt=user_prompt,
            model="qwen-turbo",
            temperature=0.4,
            max_tokens=220,
            timeout=12.0,
            system_message=system,
            user_id=user_id,
            request_type="one_sentence_chat",
            diagram_type=diagram_type,
            session_id=voice_session_id,
            endpoint_path="/ws/kitty",
        )
    except LLM_PIPELINE_ERRORS as exc:
        logger.warning("[OneSentenceTextReply] LLM failed session=%s: %s", voice_session_id, exc)
        fallback = (
            "I could not reply right now. Try a direct edit like “add a history branch”."
            if lang_code == "en"
            else "我暂时无法回复。你可以直接说“添加一个历史分支”来修改导图。"
        )
        await emit_user_ack(websocket, voice_session_id, fallback, also_omni=False)
        await safe_websocket_send(websocket, {"type": "response_text_done", "text": fallback})
        await safe_websocket_send(websocket, {"type": "response_done"})
        await fanout_voice_phase_from_outbound_type(voice_session_id, "response_done")
        return True

    reply = _extract_reply_text(result)
    if not reply:
        reply = (
            "Tell me what to change on the diagram, for example add or rename a branch."
            if lang_code == "en"
            else "告诉我你想怎么改导图，例如添加或重命名分支。"
        )

    await emit_user_ack(websocket, voice_session_id, reply, also_omni=False)
    memory.append_assistant_chunk(reply)
    memory.flush_assistant_turn()
    await safe_websocket_send(websocket, {"type": "response_text_done", "text": reply})
    await safe_websocket_send(websocket, {"type": "response_done"})
    await fanout_voice_phase_from_outbound_type(voice_session_id, "response_done")
    return True
