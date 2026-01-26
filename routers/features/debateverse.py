"""
DebateVerse Router - Debate Session Management and Streaming Endpoints
======================================================================

Provides API endpoints for creating and managing debate sessions,
streaming debater responses, and managing debate flow.

Uses MindGraph's centralized LLM infrastructure:
- Rate limiting (prevents quota exhaustion)
- Load balancing (DeepSeek → Dashscope/Volcengine, Kimi → Volcengine)
- Error handling (comprehensive error parsing)
- Token tracking (automatic usage tracking)

Chinese name: 论境
English name: DebateVerse

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
import asyncio
import base64
import json
import logging
import queue
import uuid
from pathlib import Path
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from clients.tts_realtime_client import AudioFormat, SessionMode, TTSRealtimeClient
from config.database import get_db
from models.domain.debateverse import DebateMessage, DebateParticipant, DebateSession
from prompts.debateverse import get_position_generation_prompt
from routers.auth.dependencies import get_current_user_optional
from services.features.dashscope_tts import get_tts_service
from services.features.debateverse_service import DebateVerseService
from services.llm import llm_service


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/debateverse", tags=["DebateVerse"])

# Constants for TTS buffering
SENTENCE_ENDINGS = {'.', '。', '!', '！', '?', '？', '\n'}
MIN_BUFFER_SIZE = 50  # Minimum buffer size before sending
MAX_BUFFER_SIZE = 200  # Maximum buffer size (force send even without sentence ending)

# ============================================================================
# Request/Response Models
# ============================================================================

class CreateSessionRequest(BaseModel):
    """Request model for creating a debate session."""

    topic: str
    llm_assignments: Dict[str, str]  # {role: model_id}
    format: Optional[str] = 'us_parliamentary'
    language: Optional[str] = 'zh'


class JoinSessionRequest(BaseModel):
    """Request model for joining a debate session."""

    role: Optional[str] = None  # 'debater', 'judge', 'viewer'
    side: Optional[str] = None  # 'affirmative' or 'negative' (if debater)
    position: Optional[int] = None  # 1 or 2 (if debater)


class SendMessageRequest(BaseModel):
    """Request model for sending a message in a debate session."""

    content: str


class AdvanceStageRequest(BaseModel):
    """Request model for advancing debate stage."""

    new_stage: str


# ============================================================================
# Streaming Implementation
# ============================================================================

async def stream_debater_response(
    session_id: str,
    participant_id: int,
    stage: str,
    language: str = 'zh',
    user_id: Optional[int] = None
):
    """
    Stream debater response using DebateVerseService.

    Yields SSE-formatted chunks:
    - {"type": "thinking", "content": "..."} - Reasoning/thinking content
    - {"type": "token", "content": "..."} - Response content
    - {"type": "usage", "usage": {...}} - Token usage stats
    - {"type": "audio_url", "url": "..."} - TTS audio URL (after generation)
    - {"type": "done"} - Stream complete
    - {"type": "error", "error": "..."} - Error occurred
    """
    db = next(get_db())
    try:
        service = DebateVerseService(session_id, db)

        # Build context-aware messages
        context_builder = service.context_builder
        messages = context_builder.build_debater_messages(
            participant_id=participant_id,
            stage=stage,
            language=language
        )

        # Get participant and model
        participant = db.query(DebateParticipant).filter_by(id=participant_id).first()

        if not participant:
            yield f'data: {json.dumps({"type": "error", "error": "Participant not found"})}\n\n'
            return

        model = participant.model_id or 'qwen'

        # Disable thinking for Kimi model
        enable_thinking = model.lower() != 'kimi'

        # Stream from LLM service and collect content

        full_content = ""
        full_thinking = ""

        # Initialize TTS streaming if available
        tts_service = get_tts_service()
        tts_available = tts_service.is_available()
        tts_client = None
        tts_audio_chunks = []
        tts_audio_queue = asyncio.Queue()

        # Setup TTS client with callback to collect audio chunks
        if tts_available:
            try:
                # Prioritize role over model_id for voice selection
                # Judges always use Neil voice regardless of underlying model
                if participant.role == 'judge':
                    voice = tts_service.get_voice_for_model('judge')
                else:
                    voice = tts_service.get_voice_for_model(model)

                def on_audio_chunk(audio_bytes: bytes):
                    """Callback to collect audio chunks"""
                    tts_audio_chunks.append(audio_bytes)
                    # Also queue for streaming
                    try:
                        tts_audio_queue.put_nowait(audio_bytes)
                    except queue.Full:
                        pass

                if not tts_service.api_key:
                    raise ValueError("TTS service API key is not configured")
                tts_client = TTSRealtimeClient(
                    api_key=tts_service.api_key,
                    model='qwen3-tts-flash-realtime',
                    voice=voice,
                    mode=SessionMode.COMMIT,  # Use COMMIT mode for better control
                    response_format=AudioFormat.MP3_24000HZ_MONO,
                    sample_rate=24000,
                    language_type=None,
                    on_audio_chunk=on_audio_chunk,
                )
                logger.info(
                    "[DEBATEVERSE] TTS client initialized: participant_id=%s, role=%s, model_id=%s, voice=%s",
                    participant_id, participant.role, model, voice
                )
            except Exception as tts_init_error:
                logger.error("[DEBATEVERSE] TTS initialization error: %s", tts_init_error, exc_info=True)
                tts_client = None
                tts_available = False

        # Start TTS connection when first token arrives
        tts_started = False
        tts_text_buffer = ""  # Buffer text for fluent TTS
        tts_pending_commit = False  # Track if we have uncommitted text

        # Use module-level constants for sentence endings and buffer sizes

        async def flush_tts_buffer(force: bool = False, should_commit: bool = True):
            """Flush TTS buffer when we have a complete sentence or buffer is full"""
            nonlocal tts_text_buffer, tts_pending_commit
            if not tts_client or not tts_started or not tts_text_buffer:
                return

            text_to_send = None

            if force:
                # Force flush everything
                text_to_send = tts_text_buffer
                tts_text_buffer = ""
            elif len(tts_text_buffer) >= MIN_BUFFER_SIZE:
                # Check if buffer ends with sentence punctuation
                if tts_text_buffer[-1] in SENTENCE_ENDINGS:
                    text_to_send = tts_text_buffer
                    tts_text_buffer = ""
                # Or if buffer is getting too large
                elif len(tts_text_buffer) >= MAX_BUFFER_SIZE:
                    # Find last sentence ending in buffer (look back further)
                    last_sentence_end = -1
                    for i in range(len(tts_text_buffer) - 1, max(0, len(tts_text_buffer) - 100), -1):
                        if tts_text_buffer[i] in SENTENCE_ENDINGS:
                            last_sentence_end = i + 1
                            break

                    if last_sentence_end > 0:
                        # Flush up to sentence end
                        text_to_send = tts_text_buffer[:last_sentence_end]
                        tts_text_buffer = tts_text_buffer[last_sentence_end:]
                    else:
                        # No sentence ending found, flush everything
                        text_to_send = tts_text_buffer
                        tts_text_buffer = ""

            if text_to_send and text_to_send.strip():
                try:
                    await tts_client.append_text(text_to_send)
                    tts_pending_commit = True
                    logger.debug(
                        "[DEBATEVERSE] TTS appended %s chars: %s...",
                        len(text_to_send),
                        text_to_send[:50]
                    )

                    # In COMMIT mode, commit after appending to trigger synthesis
                    # Only commit if should_commit is True (for sentence boundaries)
                    if should_commit and tts_client.mode == SessionMode.COMMIT and tts_pending_commit:
                        await tts_client.commit_text()
                        tts_pending_commit = False
                        logger.debug("[DEBATEVERSE] TTS committed text buffer")
                except Exception as tts_error:
                    logger.warning("[DEBATEVERSE] TTS append error: %s", tts_error)

        # Stream LLM tokens and feed to TTS concurrently
        async for chunk in llm_service.chat_stream(
            messages=messages,
            model=model,
            temperature=0.7,
            max_tokens=2000,
            enable_thinking=enable_thinking,
            yield_structured=True,
            user_id=user_id,
            request_type='debateverse',
            endpoint_path=f'/api/debateverse/sessions/{session_id}/stream'
        ):
            if isinstance(chunk, dict):
                chunk_type = chunk.get('type')
                if chunk_type == 'token':
                    token_content = chunk.get('content', '')
                    full_content += token_content

                    # Start TTS connection on first token
                    if tts_client and not tts_started:
                        try:
                            await tts_client.connect()
                            await tts_client.wait_for_session_created()
                            tts_started = True
                            logger.info("[DEBATEVERSE] TTS streaming started")
                        except Exception as tts_start_error:
                            logger.error("[DEBATEVERSE] TTS start error: %s", tts_start_error, exc_info=True)
                            tts_client = None

                    # Buffer text for fluent TTS (send on sentence boundaries)
                    if tts_client and tts_started and token_content:
                        tts_text_buffer += token_content
                        # Try to flush buffer if we have a complete sentence
                        await flush_tts_buffer()

                    # Yield any audio chunks that arrived
                    while not tts_audio_queue.empty():
                        try:
                            audio_chunk = tts_audio_queue.get_nowait()
                            audio_b64 = base64.b64encode(audio_chunk).decode('utf-8')
                            yield f'data: {json.dumps({"type": "audio_chunk", "data": audio_b64})}\n\n'
                        except queue.Empty:
                            break

                elif chunk_type == 'thinking':
                    full_thinking += chunk.get('content', '')
                yield f'data: {json.dumps(chunk)}\n\n'

        # Finish TTS session and collect remaining audio
        if tts_client and tts_started:
            try:
                # Flush any remaining buffered text
                await flush_tts_buffer(force=True, should_commit=True)

                # In COMMIT mode, commit any remaining uncommitted text before finishing
                if tts_client.mode == SessionMode.COMMIT and tts_pending_commit:
                    await tts_client.commit_text()
                    tts_pending_commit = False

                # Also commit any remaining text in buffer
                if tts_client.mode == SessionMode.COMMIT and tts_text_buffer:
                    await tts_client.append_text(tts_text_buffer)
                    await tts_client.commit_text()
                    tts_text_buffer = ""

                await tts_client.finish_session()
                await tts_client.wait_for_response_done(timeout=10.0)

                # Yield any remaining audio chunks
                while not tts_audio_queue.empty():
                    try:
                        audio_chunk = tts_audio_queue.get_nowait()
                        audio_b64 = base64.b64encode(audio_chunk).decode('utf-8')
                        yield f'data: {json.dumps({"type": "audio_chunk", "data": audio_b64})}\n\n'
                    except queue.Empty:
                        break

                await tts_client.close()
            except Exception as tts_finish_error:
                logger.error("[DEBATEVERSE] TTS finish error: %s", tts_finish_error, exc_info=True)

        # Save message to database
        session = db.query(DebateSession).filter_by(id=session_id).first()
        if not session:
            yield f'data: {json.dumps({"type": "error", "error": "Session not found"})}\n\n'
            return

        round_number = service.get_next_round_number(stage)
        message_type = service.get_message_type_for_stage(stage)

        message = DebateMessage(
            session_id=session_id,
            participant_id=participant_id,
            content=full_content,
            thinking=full_thinking if full_thinking else None,
            stage=stage,
            round_number=round_number,
            message_type=message_type
        )
        db.add(message)
        db.flush()  # Flush to get message ID

        # Generate TTS audio file from full content (fallback if streaming didn't work)
        if tts_available and full_content.strip():
            try:
                audio_dir = Path("static/debateverse_audio")
                audio_dir.mkdir(parents=True, exist_ok=True)
                audio_filename = f"{session_id}_{message.id}_{uuid.uuid4().hex[:8]}.mp3"
                audio_path = audio_dir / audio_filename

                # Generate TTS audio from full content
                audio_file = await tts_service.synthesize_to_file(
                    text=full_content,
                    output_path=audio_path,
                    model_id=model,
                )

                if audio_file:
                    # Update message with audio URL
                    message.audio_url = f"/static/debateverse_audio/{audio_filename}"
                    db.commit()

                    # Yield audio URL to client
                    yield f'data: {json.dumps({"type": "audio_url", "url": message.audio_url})}\n\n'
                    logger.info(
                        "[DEBATEVERSE] Generated TTS audio for message %s: %s",
                        message.id,
                        message.audio_url
                    )
                else:
                    db.commit()
                    logger.warning("[DEBATEVERSE] TTS generation failed for message %s", message.id)
            except Exception as tts_error:
                # Don't fail the whole request if TTS fails
                logger.error("[DEBATEVERSE] TTS error: %s", tts_error, exc_info=True)
                db.commit()
        else:
            db.commit()

        yield f'data: {json.dumps({"type": "done"})}\n\n'

    except asyncio.CancelledError:
        logger.info("[DEBATEVERSE] Stream cancelled for participant %s", participant_id)
        raise
    except Exception as e:
        logger.error("[DEBATEVERSE] Streaming error: %s", e, exc_info=True)
        yield f'data: {json.dumps({"type": "error", "error": str(e)})}\n\n'
    finally:
        db.close()


# ============================================================================
# API Endpoints
# ============================================================================

@router.post("/sessions")
async def create_session(
    request: CreateSessionRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_optional)
):
    """Create a new debate session."""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        service = DebateVerseService("", db)  # Will be set after creation
        session = service.create_debate_session(
            topic=request.topic,
            user_id=current_user.id,
            llm_assignments=request.llm_assignments,
            format=request.format or 'us_parliamentary'
        )

        return {
            "session_id": session.id,
            "topic": session.topic,
            "current_stage": session.current_stage,
            "status": session.status,
            "created_at": session.created_at.isoformat()
        }
    except Exception as e:
        logger.error("Error creating debate session: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    db: Session = Depends(get_db),
    _current_user = Depends(get_current_user_optional)
):
    """Get debate session with messages and participants."""
    session = db.query(DebateSession).filter_by(id=session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Get participants
    participants = db.query(DebateParticipant).filter_by(session_id=session_id).all()

    # Get messages
    messages = db.query(DebateMessage).filter_by(session_id=session_id).order_by(
        DebateMessage.created_at
    ).all()

    return {
        "session": {
            "id": session.id,
            "topic": session.topic,
            "current_stage": session.current_stage,
            "status": session.status,
            "coin_toss_result": session.coin_toss_result,
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat()
        },
        "participants": [
            {
                "id": p.id,
                "name": p.name,
                "role": p.role,
                "side": p.side,
                "is_ai": p.is_ai,
                "model_id": p.model_id
            }
            for p in participants
        ],
        "messages": [
            {
                "id": m.id,
                "participant_id": m.participant_id,
                "content": m.content,
                "thinking": m.thinking,
                "stage": m.stage,
                "round_number": m.round_number,
                "message_type": m.message_type,
                "audio_url": m.audio_url,
                "created_at": m.created_at.isoformat()
            }
            for m in messages
        ]
    }


@router.post("/sessions/{session_id}/coin-toss")
async def coin_toss(
    session_id: str,
    db: Session = Depends(get_db),
    _current_user = Depends(get_current_user_optional)
):
    """Execute coin toss to determine speaking order."""
    service = DebateVerseService(session_id, db)
    result = service.coin_toss()

    return {
        "result": result,
        "message": "affirmative_first" if result == "affirmative_first" else "negative_first"
    }


@router.get("/sessions/{session_id}/generate-positions")
async def generate_positions(
    session_id: str,
    language: str = Query('zh', description="Language for position generation"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_optional)
):
    """
    Generate debate positions using Doubao LLM with SSE streaming.

    Uses the topic from the session (session_id already contains the topic).
    The user's topic/statement is included in the prompt to generate positions.

    Yields SSE-formatted chunks:
    - {"type": "token", "content": "..."} - Position content tokens
    - {"type": "done"} - Stream complete
    - {"type": "error", "error": "..."} - Error occurred
    """
    async def generate():
        try:
            # Get session - session_id already contains the topic
            session = db.query(DebateSession).filter_by(id=session_id).first()
            if not session:
                yield f'data: {json.dumps({"type": "error", "error": "Session not found"})}\n\n'
                return

            # Get topic from session (this is the user's statement/topic)
            debate_topic = session.topic or "辩论主题"

            logger.info(
                "[DEBATEVERSE] Generating positions for session %s, topic: %s",
                session_id,
                debate_topic
            )

            # Build prompt with user's topic/statement from the session
            prompt = get_position_generation_prompt(topic=debate_topic, language=language)

            # Stream from Doubao LLM
            full_content = ""
            async for chunk in llm_service.chat_stream(
                messages=[{"role": "user", "content": prompt}],
                model='doubao',
                temperature=0.7,
                max_tokens=1000,
                enable_thinking=False,
                yield_structured=True,
                user_id=current_user.id if current_user else None,
                request_type='debateverse',
                endpoint_path=f'/api/debateverse/sessions/{session_id}/generate-positions'
            ):
                if isinstance(chunk, dict):
                    chunk_type = chunk.get('type')
                    if chunk_type == 'token':
                        content = chunk.get('content', '')
                        full_content += content
                        yield f'data: {json.dumps({"type": "token", "content": content})}\n\n'

            yield f'data: {json.dumps({"type": "done"})}\n\n'

        except asyncio.CancelledError:
            logger.info("[DEBATEVERSE] Position generation cancelled for session %s", session_id)
            raise
        except Exception as e:
            logger.error("[DEBATEVERSE] Position generation error: %s", e, exc_info=True)
            yield f'data: {json.dumps({"type": "error", "error": str(e)})}\n\n'
        finally:
            db.close()

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/sessions/{session_id}/advance-stage")
async def advance_stage(
    session_id: str,
    request: AdvanceStageRequest,
    db: Session = Depends(get_db),
    _current_user = Depends(get_current_user_optional)
):
    """Advance debate to next stage (judge only)."""
    service = DebateVerseService(session_id, db)
    success = service.advance_stage(request.new_stage)

    if not success:
        raise HTTPException(status_code=400, detail="Invalid stage transition")

    return {"success": True, "new_stage": request.new_stage}


@router.post("/sessions/{session_id}/messages")
async def send_user_message(
    session_id: str,
    request: SendMessageRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_optional)
):
    """Send a user message in the debate session."""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")


    # Get session
    session = db.query(DebateSession).filter_by(id=session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Find user participant
    user_participant = db.query(DebateParticipant).filter_by(
        session_id=session_id,
        user_id=current_user.id,
        is_ai=False
    ).first()

    if not user_participant:
        raise HTTPException(status_code=403, detail="User is not a participant in this session")

    # Get current stage and determine message type
    current_stage = session.current_stage
    service = DebateVerseService(session_id, db)
    round_number = service.get_next_round_number(current_stage)
    message_type = service.get_message_type_for_stage(current_stage)

    # Create message
    message = DebateMessage(
        session_id=session_id,
        participant_id=user_participant.id,
        content=request.content,
        stage=current_stage,
        round_number=round_number,
        message_type=message_type
    )
    db.add(message)
    db.commit()

    logger.info("User %s sent message in session %s", current_user.id, session_id)

    return {
        "success": True,
        "message_id": message.id,
        "message": {
            "id": message.id,
            "participant_id": message.participant_id,
            "content": message.content,
            "stage": message.stage,
            "round_number": message.round_number,
            "message_type": message.message_type,
            "created_at": message.created_at.isoformat()
        }
    }


@router.post("/next")
async def trigger_next(
    session_id: str = Query(...),
    language: str = Query('zh'),
    db: Session = Depends(get_db),
    _current_user = Depends(get_current_user_optional)
):
    """
    Trigger next conversation in debate.
    Returns next speaker info for immediate streaming, or indicates stage completion.
    """
    logger.info("Trigger next called for session %s", session_id)

    session = db.query(DebateSession).filter_by(id=session_id).first()
    if not session:
        logger.error("Session %s not found in database", session_id)
        raise HTTPException(status_code=404, detail="Session not found")

    logger.info("Session found: %s, current_stage: %s", session.id, session.current_stage)

    service = DebateVerseService(session_id, db)

    # Get next speaker for current stage
    next_speaker = service.get_next_speaker(session.current_stage)

    if next_speaker:
        # Return next speaker info - frontend will immediately trigger stream
        return {
            "action": "trigger_speaker",
            "has_next_speaker": True,
            "participant_id": next_speaker.id,
            "participant_name": next_speaker.name,
            "participant_role": next_speaker.role,
            "participant_side": next_speaker.side,
            "stage": session.current_stage,
            "language": language
        }
    else:
        # Stage is complete, return next stage info
        stage_order = ['setup', 'coin_toss', 'opening', 'rebuttal', 'cross_exam', 'closing', 'judgment', 'completed']
        current_index = stage_order.index(session.current_stage) if session.current_stage in stage_order else -1

        if current_index < len(stage_order) - 1:
            next_stage = stage_order[current_index + 1]
            return {
                "action": "advance_stage",
                "has_next_speaker": False,
                "stage_complete": True,
                "next_stage": next_stage,
                "current_stage": session.current_stage
            }
        else:
            return {
                "action": "complete",
                "has_next_speaker": False,
                "stage_complete": True,
                "debate_complete": True,
                "current_stage": session.current_stage
            }


@router.post("/sessions/{session_id}/stream/{participant_id}")
async def stream_debater(
    session_id: str,
    participant_id: int,
    stage: str,
    language: str = 'zh',
    _db: Session = Depends(get_db),
    current_user = Depends(get_current_user_optional)
):
    """Stream debater response for a specific participant."""
    user_id = current_user.id if current_user else None

    return StreamingResponse(
        stream_debater_response(
            session_id=session_id,
            participant_id=participant_id,
            stage=stage,
            language=language,
            user_id=user_id
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.get("/sessions")
async def list_sessions(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_optional),
    limit: int = 20,
    offset: int = 0
):
    """List user's debate sessions."""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")

    sessions = db.query(DebateSession).filter_by(
        user_id=current_user.id
    ).order_by(
        DebateSession.updated_at.desc()
    ).offset(offset).limit(limit).all()

    return {
        "sessions": [
            {
                "id": s.id,
                "topic": s.topic,
                "current_stage": s.current_stage,
                "status": s.status,
                "created_at": s.created_at.isoformat(),
                "updated_at": s.updated_at.isoformat()
            }
            for s in sessions
        ],
        "total": db.query(DebateSession).filter_by(user_id=current_user.id).count()
    }
