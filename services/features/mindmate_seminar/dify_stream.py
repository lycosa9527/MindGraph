"""
Stream shared MindMate (Dify) responses to a collab room.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Optional

from clients.dify_http_errors import (
    dify_stream_chunk_is_upstream_outage,
    mindmate_turn_on_backup,
    mindmate_upstream_error_code,
)
from services.diagram.generation_session_registry import register_generation_session
from services.dify.org_dify_inputs import apply_persona_inputs_for_organization_id
from services.dify.org_mindmate_client import resolve_mindmate_dify_stream_short_lived
from services.features.mindmate_seminar.config import (
    MINDMATE_COLLAB_STREAM_FLUSH_CHARS,
    MINDMATE_COLLAB_STREAM_FLUSH_MS,
)
from services.features.mindmate_seminar.dify_identity import mindmate_seminar_dify_user_id
from services.features.mindmate_seminar.dify_stream_control import (
    clear_dify_stream_abort,
    clear_dify_stream_task,
    is_dify_stream_aborted,
    refresh_dify_stream_lock,
    register_dify_stream_task,
    release_dify_stream_lock,
)
from services.features.mindmate_seminar.manager_access import get_mindmate_seminar_manager
from services.features.mindmate_seminar.redis_keys import normalize_collab_code
from services.features.mindmate_seminar.reply_artifacts import schedule_teaching_reply_artifact
from services.features.mindmate_seminar.stream_coalesce import SeminarStreamCoalescer
from services.features.mindmate_seminar.ws_broadcast import broadcast_to_all
from services.infrastructure.http.sse_upstream_keepalive import iter_upstream_with_keepalive
from services.mindmate.chain_of_thought import (
    MindmateThinkingGate,
    organization_shows_chain_of_thought,
)
from services.mindmate.teaching_design_flag import (
    ensure_teaching_instruction_marker,
    is_teaching_instruction_text,
    mindmate_meta_from_workflow_chunk,
)
from services.redis.cache.redis_org_cache import org_cache
from services.utils.error_types import DATABASE_ERRORS

logger = logging.getLogger(__name__)

# How often to wake while Dify is silent when paints are not batched.
_QUIET_UPSTREAM_WAIT_SECONDS = 15.0


def _answer_with_teaching_flag(parts: list[str], teaching_flagged: bool) -> str:
    """Stamp the durable marker when workflow outputs flag a lesson-design reply."""
    text = "".join(parts)
    if not teaching_flagged:
        return text
    return ensure_teaching_instruction_marker(text)


async def _store_partial_assistant(
    session_id: str,
    text: str,
    room_code: str,
) -> tuple[Optional[int], Optional[int]]:
    """Keep an interrupted MindMate reply. Returns ``(id, prev_id)`` when saved."""
    cleaned = text.strip()
    if not cleaned:
        return None, None
    try:
        saved = await get_mindmate_seminar_manager().persist_message(
            session_id,
            role="assistant",
            content=cleaned,
            sender_user_id=None,
            room_code=room_code,
        )
    except DATABASE_ERRORS as exc:
        logger.warning(
            "[MindmateSeminarDify] partial save failed session=%s: %s",
            session_id,
            exc,
        )
        return None, None
    return saved.id, saved.prev_id


async def _broadcast_aborted_end(
    code: str,
    partial: str,
    message_id: Optional[int],
    prev_id: Optional[int],
) -> None:
    frame: dict[str, Any] = {
        "type": "ai_message_end",
        "content": partial,
        "aborted": True,
    }
    if message_id is not None:
        frame["id"] = message_id
        frame["prev_id"] = prev_id
    await broadcast_to_all(code, frame)


def _upstream_wait_seconds() -> float:
    """Wake often enough to release text held while Dify is quiet."""
    flush_ms = MINDMATE_COLLAB_STREAM_FLUSH_MS
    if flush_ms <= 0:
        return _QUIET_UPSTREAM_WAIT_SECONDS
    return flush_ms / 1000


async def _remember_seminar_library_owner(
    *,
    org_id: Optional[int],
    session_id: str,
    sender_user_id: int,
    conversation_id: Optional[str],
) -> None:
    """Record who asked, so generate_dingtalk can save into that user's library.

    The Dify ``user`` is the shared room id. Without this registry row the tool
    cannot tell which participant owns the diagram and the reply stays a preview.
    """
    if sender_user_id <= 0:
        return
    await register_generation_session(
        channel="seminar",
        dify_user_id=mindmate_seminar_dify_user_id(org_id, session_id),
        user_id=sender_user_id,
        organization_id=org_id,
        conversation_id=conversation_id,
    )


async def _broadcast_answer_delta(code: str, sender_user_id: int, delta: Optional[str]) -> None:
    """Paint one combined slice of the in-progress answer and keep the stream lock."""
    if not delta:
        return
    await refresh_dify_stream_lock(code)
    await broadcast_to_all(
        code,
        {
            "type": "ai_message_chunk",
            "content": delta,
            "sender_user_id": sender_user_id,
        },
    )


async def stream_assistant_reply(
    *,
    code: str,
    session_id: str,
    org_id: Optional[int],
    user_message: str,
    sender_user_id: int,
    conversation_id: Optional[str],
    conversation_server: Optional[int] = None,
) -> None:
    """Background task: call Dify and fan-out chunks to the room."""
    mgr = get_mindmate_seminar_manager()
    dify_user = mindmate_seminar_dify_user_id(org_id, session_id)
    library_conversation = (conversation_id or "").strip() or None
    await _remember_seminar_library_owner(
        org_id=org_id,
        session_id=session_id,
        sender_user_id=sender_user_id,
        conversation_id=library_conversation,
    )
    full_answer: list[str] = []
    teaching_flagged = False
    cached_org = await org_cache.get_by_id(org_id) if org_id is not None else None
    thinking_gate = MindmateThinkingGate(organization_shows_chain_of_thought(cached_org))
    aborted = False
    outcome = "ok"
    coalescer = SeminarStreamCoalescer(
        interval_seconds=MINDMATE_COLLAB_STREAM_FLUSH_MS / 1000,
        max_held_chars=MINDMATE_COLLAB_STREAM_FLUSH_CHARS,
    )

    async def _flush_held() -> None:
        await _broadcast_answer_delta(code, sender_user_id, coalescer.flush())

    try:
        logger.info("[MindmateSeminarDify] stream started code=%s session=%s", code, session_id)
        await broadcast_to_all(
            code,
            {"type": "mindmate_chain_of_thought", "show": thinking_gate.show},
        )
        if await is_dify_stream_aborted(code):
            outcome = "aborted"
            return

        stream_target = await resolve_mindmate_dify_stream_short_lived(
            org_id,
            detail="AI service not configured",
            conversation_id=conversation_id,
            conversation_server=conversation_server,
        )
        client = stream_target.client
        if stream_target.notify_backup:
            await broadcast_to_all(code, {"type": "mindmate_failover"})
        collab_inputs: dict[str, Any] = {"mg_dify_user": dify_user}
        if conversation_id:
            collab_inputs["mg_conversation_id"] = conversation_id
        await apply_persona_inputs_for_organization_id(collab_inputs, org_id)
        stream = client.stream_chat(
            message=user_message,
            user_id=dify_user,
            conversation_id=stream_target.upstream_conversation_id,
            inputs=collab_inputs,
        )
        quiet_abort_at = time.monotonic() + _QUIET_UPSTREAM_WAIT_SECONDS
        async for chunk in iter_upstream_with_keepalive(
            stream,
            interval_seconds=_upstream_wait_seconds(),
        ):
            if not chunk:
                await _flush_held()
                now = time.monotonic()
                if now < quiet_abort_at:
                    continue
                quiet_abort_at = now + _QUIET_UPSTREAM_WAIT_SECONDS
            if await is_dify_stream_aborted(code):
                aborted = True
                outcome = "aborted"
                break
            if not chunk:
                continue
            event = chunk.get("event") if isinstance(chunk, dict) else None
            if event == "error":
                await _flush_held()
                if dify_stream_chunk_is_upstream_outage(chunk):
                    on_backup = mindmate_turn_on_backup(
                        notify_backup=stream_target.notify_backup,
                        server=stream_target.server,
                    )
                    outage_code = mindmate_upstream_error_code(on_backup=on_backup)
                    await broadcast_to_all(
                        code,
                        {"type": "error", "code": outage_code},
                    )
                    outcome = "upstream_error"
                    return
                message = str(chunk.get("message", ""))
                await broadcast_to_all(
                    code,
                    {"type": "error", "code": "dify_error", "message": message},
                )
                outcome = "dify_error"
                return
            answer = chunk.get("answer") if isinstance(chunk, dict) else None
            conv_id = chunk.get("conversation_id") if isinstance(chunk, dict) else None
            if conv_id:
                incoming = str(conv_id).strip()
                if incoming and incoming != (library_conversation or ""):
                    library_conversation = incoming
                    await _remember_seminar_library_owner(
                        org_id=org_id,
                        session_id=session_id,
                        sender_user_id=sender_user_id,
                        conversation_id=incoming,
                    )
            if conv_id and not conversation_id:
                conversation_id = str(conv_id)
                saved_server = stream_target.server if stream_target.server is not None else 1
                await mgr.set_dify_conversation_id(
                    session_id,
                    conversation_id,
                    server=saved_server,
                )
            if isinstance(chunk, dict) and not teaching_flagged:
                if mindmate_meta_from_workflow_chunk(chunk):
                    teaching_flagged = True
            if isinstance(chunk, dict) and event == "agent_thought":
                thinking_gate.note_agent_thought(chunk)
            if isinstance(chunk, dict) and event == "message_replace":
                thinking_gate.on_message_replace()
            if answer:
                piece = thinking_gate.visible_answer(str(answer))
                if piece:
                    full_answer.append(piece)
                    await _broadcast_answer_delta(code, sender_user_id, coalescer.push(piece))
        if not aborted:
            extra_thinking = thinking_gate.closing_thinking_delta()
            if extra_thinking:
                full_answer.append(extra_thinking)
                await _broadcast_answer_delta(code, sender_user_id, coalescer.push(extra_thinking))
        if aborted:
            await _flush_held()
            partial = _answer_with_teaching_flag(full_answer, teaching_flagged)
            message_id, prev_id = await _store_partial_assistant(session_id, partial, code)
            await _broadcast_aborted_end(code, partial, message_id, prev_id)
            return
        await _flush_held()
        final_text = _answer_with_teaching_flag(full_answer, teaching_flagged)
        assistant_id: Optional[int] = None
        assistant_prev_id: Optional[int] = None
        created_stamp: Optional[str] = None
        if final_text.strip():
            saved = await mgr.persist_message(
                session_id,
                role="assistant",
                content=final_text,
                sender_user_id=None,
                room_code=code,
            )
            assistant_id = saved.id
            assistant_prev_id = saved.prev_id
            if isinstance(saved.created_at, str) and saved.created_at:
                created_stamp = saved.created_at
        end_frame: dict[str, Any] = {
            "type": "ai_message_end",
            "content": final_text,
            "id": assistant_id,
        }
        if assistant_id is not None:
            end_frame["prev_id"] = assistant_prev_id
            if created_stamp:
                end_frame["created_at"] = created_stamp
        await broadcast_to_all(code, end_frame)
        if assistant_id is not None and is_teaching_instruction_text(final_text):
            schedule_teaching_reply_artifact(
                code=code,
                session_id=session_id,
                message_id=assistant_id,
                uploader_user_id=sender_user_id,
            )
    except asyncio.CancelledError:
        outcome = "cancelled"
        await _flush_held()
        partial = _answer_with_teaching_flag(full_answer, teaching_flagged)
        message_id, prev_id = await _store_partial_assistant(session_id, partial, code)
        await _broadcast_aborted_end(code, partial, message_id, prev_id)
        raise
    except (OSError, RuntimeError, ValueError, TypeError, KeyError) as exc:
        outcome = "failed"
        logger.warning("[MindmateSeminarDify] stream failed code=%s: %s", code, exc)
        await _flush_held()
        await broadcast_to_all(code, {"type": "error", "code": "dify_error", "message": "AI response failed"})
    finally:
        logger.info("[MindmateSeminarDify] stream finished code=%s session=%s outcome=%s", code, session_id, outcome)
        await release_dify_stream_lock(code)
        await clear_dify_stream_abort(code)
        clear_dify_stream_task(code)


def schedule_assistant_reply(
    *,
    code: str,
    session_id: str,
    org_id: Optional[int],
    user_message: str,
    sender_user_id: int,
    conversation_id: Optional[str],
    conversation_server: Optional[int] = None,
) -> None:
    """Start a background Dify stream task for the room."""
    norm = normalize_collab_code(code)
    task = asyncio.create_task(
        stream_assistant_reply(
            code=code,
            session_id=session_id,
            org_id=org_id,
            user_message=user_message,
            sender_user_id=sender_user_id,
            conversation_id=conversation_id,
            conversation_server=conversation_server,
        ),
        name=f"mindmate-seminar-dify:{norm}",
    )
    register_dify_stream_task(code, task)
