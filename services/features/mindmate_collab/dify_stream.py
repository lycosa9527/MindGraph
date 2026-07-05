"""
Stream shared MindMate (Dify) responses to a collab room.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from services.dify.org_mindmate_client import resolve_mindmate_dify_client_short_lived
from services.features.mindmate_collab.dify_stream_control import (
    clear_dify_stream_abort,
    clear_dify_stream_task,
    is_dify_stream_aborted,
    refresh_dify_stream_lock,
    register_dify_stream_task,
    release_dify_stream_lock,
)
from services.features.mindmate_collab.manager_access import get_mindmate_collab_manager
from services.features.mindmate_collab.redis_keys import normalize_collab_code
from services.features.mindmate_collab.ws_broadcast import broadcast_to_all
from services.infrastructure.http.sse_upstream_keepalive import iter_upstream_with_keepalive

logger = logging.getLogger(__name__)


def mindmate_collab_dify_user_id(org_id: Optional[int], session_id: str) -> str:
    """Build stable Dify user id for a shared collab conversation."""
    org_part = str(org_id) if org_id is not None else "0"
    return f"mindmate_collab_{org_part}_{session_id}"


async def _broadcast_aborted_end(code: str, partial: str) -> None:
    await broadcast_to_all(
        code,
        {
            "type": "ai_message_end",
            "content": partial,
            "aborted": True,
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
) -> None:
    """Background task: call Dify and fan-out chunks to the room."""
    mgr = get_mindmate_collab_manager()
    dify_user = mindmate_collab_dify_user_id(org_id, session_id)
    full_answer: list[str] = []
    aborted = False

    try:
        if await is_dify_stream_aborted(code):
            aborted = True
            return

        client = await resolve_mindmate_dify_client_short_lived(org_id, detail="AI service not configured")
        stream = client.stream_chat(
            message=user_message,
            user_id=dify_user,
            conversation_id=conversation_id,
            inputs={"mg_dify_user": dify_user},
        )
        async for chunk in iter_upstream_with_keepalive(stream, interval_seconds=15.0):
            if await is_dify_stream_aborted(code):
                aborted = True
                break
            if not chunk:
                continue
            event = chunk.get("event") if isinstance(chunk, dict) else None
            if event == "error":
                await broadcast_to_all(
                    code,
                    {"type": "error", "code": "dify_error", "message": str(chunk.get("message", ""))},
                )
                return
            answer = chunk.get("answer") if isinstance(chunk, dict) else None
            conv_id = chunk.get("conversation_id") if isinstance(chunk, dict) else None
            if conv_id and not conversation_id:
                conversation_id = str(conv_id)
                await mgr.set_dify_conversation_id(session_id, conversation_id)
            if answer:
                await refresh_dify_stream_lock(code)
                full_answer.append(str(answer))
                await broadcast_to_all(
                    code,
                    {
                        "type": "ai_message_chunk",
                        "content": str(answer),
                        "sender_user_id": sender_user_id,
                    },
                )
        if aborted:
            await _broadcast_aborted_end(code, "".join(full_answer))
            return
        final_text = "".join(full_answer)
        assistant_id: Optional[int] = None
        if final_text.strip():
            saved = await mgr.persist_message(
                session_id,
                role="assistant",
                content=final_text,
                sender_user_id=None,
            )
            assistant_id = saved.id
        await broadcast_to_all(
            code,
            {
                "type": "ai_message_end",
                "content": final_text,
                "id": assistant_id,
            },
        )
    except asyncio.CancelledError:
        await _broadcast_aborted_end(code, "".join(full_answer))
        raise
    except (OSError, RuntimeError, ValueError, TypeError, KeyError) as exc:
        logger.warning("[MindmateCollabDify] stream failed code=%s: %s", code, exc)
        await broadcast_to_all(code, {"type": "error", "code": "dify_error", "message": "AI response failed"})
    finally:
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
        ),
        name=f"mindmate-collab-dify:{norm}",
    )
    register_dify_stream_task(code, task)
