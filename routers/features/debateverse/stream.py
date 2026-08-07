"""DebateVerse SSE streaming with short RLS sessions around LLM/TTS.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import queue
import uuid
from pathlib import Path
from typing import Any, AsyncIterator, Optional

from sqlalchemy import select

from clients.tts_realtime_client import AudioFormat, SessionMode, TTSRealtimeClient
from models.domain.debateverse import DebateMessage, DebateParticipant, DebateSession
from services.features.dashscope_tts import get_tts_service
from services.features.debateverse_service import DebateVerseService
from services.llm import llm_service
from services.llm.llm_utils import stream_enable_thinking
from services.utils.error_types import BACKGROUND_INFRA_ERRORS, DATABASE_ERRORS
from utils.db.session_open import user_rls_session

logger = logging.getLogger(__name__)

SENTENCE_ENDINGS = {".", "。", "!", "！", "?", "？", "\n"}
MIN_BUFFER_SIZE = 50
MAX_BUFFER_SIZE = 200


async def _load_stream_context(
    *,
    session_id: str,
    participant_id: int,
    stage: str,
    language: str,
    user_id: int,
) -> tuple[list[dict[str, str]], str, str] | tuple[None, str, None]:
    """Short RLS: build LLM messages + participant model/role. Returns error detail on failure."""
    async with user_rls_session(user_id) as db:
        service = DebateVerseService(session_id, db)
        try:
            messages = await service.context_builder.build_debater_messages(
                participant_id=participant_id,
                stage=stage,
                language=language,
            )
        except ValueError as exc:
            return None, str(exc), None

        participant = (
            await db.execute(select(DebateParticipant).where(DebateParticipant.id == participant_id))
        ).scalar_one_or_none()
        if not participant:
            return None, "Participant not found", None
        model = participant.model_id or "qwen"
        role = participant.role or "debater"
        return messages, model, role


async def _persist_stream_message(
    *,
    session_id: str,
    participant_id: int,
    stage: str,
    user_id: int,
    full_content: str,
    full_thinking: str,
    audio_url: Optional[str],
) -> tuple[Optional[int], Optional[str]]:
    """Short RLS: insert debate message. Returns (message_id, error)."""
    async with user_rls_session(user_id) as db:
        service = DebateVerseService(session_id, db)
        session = (await db.execute(select(DebateSession).where(DebateSession.id == session_id))).scalar_one_or_none()
        if not session:
            return None, "Session not found"

        round_number = await service.get_next_round_number(stage)
        message_type = service.get_message_type_for_stage(stage)
        message = DebateMessage(
            session_id=session_id,
            participant_id=participant_id,
            content=full_content,
            thinking=full_thinking if full_thinking else None,
            stage=stage,
            round_number=round_number,
            message_type=message_type,
            audio_url=audio_url,
        )
        db.add(message)
        try:
            await db.commit()
        except DATABASE_ERRORS as commit_err:
            await db.rollback()
            logger.error("[DEBATEVERSE] Failed to commit message: %s", commit_err)
            return None, "Internal server error"
        return int(message.id), None


async def stream_debater_response(
    session_id: str,
    participant_id: int,
    stage: str,
    language: str = "zh",
    user_id: Optional[int] = None,
) -> AsyncIterator[str]:
    """
    Stream debater response without holding a DB transaction across LLM/TTS.

    Yields SSE-formatted chunks (thinking / token / audio / done / error).
    """
    if user_id is None:
        yield f"data: {json.dumps({'type': 'error', 'error': 'Unauthorized'})}\n\n"
        return

    try:
        loaded = await _load_stream_context(
            session_id=session_id,
            participant_id=participant_id,
            stage=stage,
            language=language,
            user_id=user_id,
        )
    except DATABASE_ERRORS as exc:
        logger.error("[DEBATEVERSE] Stream context load failed: %s", exc, exc_info=True)
        yield f"data: {json.dumps({'type': 'error', 'error': 'Internal server error'})}\n\n"
        return

    messages, model_or_err, role = loaded
    if messages is None or role is None:
        yield f"data: {json.dumps({'type': 'error', 'error': model_or_err})}\n\n"
        return
    model = model_or_err

    enable_thinking = stream_enable_thinking(model)
    full_content = ""
    full_thinking = ""

    tts_service = get_tts_service()
    tts_available = tts_service.is_available()
    tts_client: Any = None
    tts_audio_chunks: list[bytes] = []
    tts_audio_queue: asyncio.Queue[bytes] = asyncio.Queue()

    if tts_available:
        try:
            voice = (
                tts_service.get_voice_for_model("judge") if role == "judge" else tts_service.get_voice_for_model(model)
            )

            def on_audio_chunk(audio_bytes: bytes) -> None:
                tts_audio_chunks.append(audio_bytes)
                try:
                    tts_audio_queue.put_nowait(audio_bytes)
                except queue.Full:
                    pass

            if not tts_service.api_key:
                raise ValueError("TTS service API key is not configured")
            tts_client = TTSRealtimeClient(
                api_key=tts_service.api_key,
                model="qwen3-tts-flash-realtime",
                voice=voice,
                mode=SessionMode.COMMIT,
                response_format=AudioFormat.MP3_24000HZ_MONO,
                sample_rate=24000,
                language_type=None,
                on_audio_chunk=on_audio_chunk,
            )
            logger.info(
                "[DEBATEVERSE] TTS client initialized: participant_id=%s, role=%s, model_id=%s, voice=%s",
                participant_id,
                role,
                model,
                voice,
            )
        except BACKGROUND_INFRA_ERRORS as tts_init_error:
            logger.error(
                "[DEBATEVERSE] TTS initialization error: %s",
                tts_init_error,
                exc_info=True,
            )
            tts_client = None
            tts_available = False

    tts_started = False
    tts_text_buffer = ""
    tts_pending_commit = False

    async def flush_tts_buffer(force: bool = False, should_commit: bool = True) -> None:
        nonlocal tts_text_buffer, tts_pending_commit
        if not tts_client or not tts_started or not tts_text_buffer:
            return

        text_to_send = None
        if force:
            text_to_send = tts_text_buffer
            tts_text_buffer = ""
        elif len(tts_text_buffer) >= MIN_BUFFER_SIZE:
            if tts_text_buffer[-1] in SENTENCE_ENDINGS:
                text_to_send = tts_text_buffer
                tts_text_buffer = ""
            elif len(tts_text_buffer) >= MAX_BUFFER_SIZE:
                last_sentence_end = -1
                for i in range(len(tts_text_buffer) - 1, max(0, len(tts_text_buffer) - 100), -1):
                    if tts_text_buffer[i] in SENTENCE_ENDINGS:
                        last_sentence_end = i + 1
                        break
                if last_sentence_end > 0:
                    text_to_send = tts_text_buffer[:last_sentence_end]
                    tts_text_buffer = tts_text_buffer[last_sentence_end:]
                else:
                    text_to_send = tts_text_buffer
                    tts_text_buffer = ""

        if text_to_send and text_to_send.strip():
            try:
                await tts_client.append_text(text_to_send)
                tts_pending_commit = True
                if should_commit and tts_client.mode == SessionMode.COMMIT and tts_pending_commit:
                    await tts_client.commit_text()
                    tts_pending_commit = False
            except BACKGROUND_INFRA_ERRORS as tts_error:
                logger.warning("[DEBATEVERSE] TTS append error: %s", tts_error)

    try:
        async for chunk in llm_service.chat_stream(
            messages=messages,
            model=model,
            temperature=0.7,
            max_tokens=2000,
            enable_thinking=enable_thinking,
            yield_structured=True,
            user_id=user_id,
            request_type="debateverse",
            endpoint_path=f"/api/debateverse/sessions/{session_id}/stream",
        ):
            if isinstance(chunk, dict):
                chunk_type = chunk.get("type")
                if chunk_type == "token":
                    token_content = chunk.get("content", "")
                    full_content += token_content

                    if tts_client and not tts_started:
                        try:
                            await tts_client.connect()
                            await tts_client.wait_for_session_created()
                            tts_started = True
                            logger.info("[DEBATEVERSE] TTS streaming started")
                        except BACKGROUND_INFRA_ERRORS as tts_start_error:
                            logger.error(
                                "[DEBATEVERSE] TTS start error: %s",
                                tts_start_error,
                                exc_info=True,
                            )
                            tts_client = None

                    if tts_client and tts_started and token_content:
                        tts_text_buffer += token_content
                        await flush_tts_buffer()

                    while not tts_audio_queue.empty():
                        try:
                            audio_chunk = tts_audio_queue.get_nowait()
                            audio_b64 = base64.b64encode(audio_chunk).decode("utf-8")
                            yield f"data: {json.dumps({'type': 'audio_chunk', 'data': audio_b64})}\n\n"
                        except queue.Empty:
                            break

                elif chunk_type == "thinking":
                    full_thinking += chunk.get("content", "")
                yield f"data: {json.dumps(chunk)}\n\n"

        if tts_client and tts_started:
            try:
                await flush_tts_buffer(force=True, should_commit=True)
                if tts_client.mode == SessionMode.COMMIT and tts_pending_commit:
                    await tts_client.commit_text()
                    tts_pending_commit = False
                if tts_client.mode == SessionMode.COMMIT and tts_text_buffer:
                    await tts_client.append_text(tts_text_buffer)
                    await tts_client.commit_text()
                    tts_text_buffer = ""
                await tts_client.finish_session()
                await tts_client.wait_for_response_done(timeout=10.0)
                while not tts_audio_queue.empty():
                    try:
                        audio_chunk = tts_audio_queue.get_nowait()
                        audio_b64 = base64.b64encode(audio_chunk).decode("utf-8")
                        yield f"data: {json.dumps({'type': 'audio_chunk', 'data': audio_b64})}\n\n"
                    except queue.Empty:
                        break
                await tts_client.close()
            except BACKGROUND_INFRA_ERRORS as tts_finish_error:
                logger.error(
                    "[DEBATEVERSE] TTS finish error: %s",
                    tts_finish_error,
                    exc_info=True,
                )

        audio_url: Optional[str] = None
        if tts_available and full_content.strip():
            try:
                audio_dir = Path("static/debateverse_audio")
                audio_dir.mkdir(parents=True, exist_ok=True)
                audio_filename = f"{session_id}_{participant_id}_{uuid.uuid4().hex[:8]}.mp3"
                audio_path = audio_dir / audio_filename
                audio_file = await tts_service.synthesize_to_file(
                    text=full_content,
                    output_path=audio_path,
                    model_id=model,
                )
                if audio_file:
                    audio_url = f"/static/debateverse_audio/{audio_filename}"
                else:
                    logger.warning(
                        "[DEBATEVERSE] TTS file synthesis failed participant=%s",
                        participant_id,
                    )
            except BACKGROUND_INFRA_ERRORS as tts_error:
                logger.error("[DEBATEVERSE] TTS file error: %s", tts_error, exc_info=True)

        try:
            _message_id, persist_err = await _persist_stream_message(
                session_id=session_id,
                participant_id=participant_id,
                stage=stage,
                user_id=user_id,
                full_content=full_content,
                full_thinking=full_thinking,
                audio_url=audio_url,
            )
        except DATABASE_ERRORS as persist_exc:
            logger.error("[DEBATEVERSE] Persist failed: %s", persist_exc, exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'error': 'Internal server error'})}\n\n"
            return

        if persist_err:
            yield f"data: {json.dumps({'type': 'error', 'error': persist_err})}\n\n"
            return

        if audio_url:
            yield f"data: {json.dumps({'type': 'audio_url', 'url': audio_url})}\n\n"
            logger.info(
                "[DEBATEVERSE] Generated TTS audio for participant %s: %s",
                participant_id,
                audio_url,
            )

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    except asyncio.CancelledError:
        logger.info("[DEBATEVERSE] Stream cancelled for participant %s", participant_id)
        raise
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.error("[DEBATEVERSE] Streaming error: %s", exc, exc_info=True)
        yield f"data: {json.dumps({'type': 'error', 'error': 'Internal server error'})}\n\n"
