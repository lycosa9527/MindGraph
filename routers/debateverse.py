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
import json
import logging
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, HTTPException, Request, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config.database import get_db
from routers.auth.dependencies import get_current_user_optional
from services.debateverse_service import DebateVerseService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/debateverse", tags=["DebateVerse"])

# ============================================================================
# Request/Response Models
# ============================================================================

class CreateSessionRequest(BaseModel):
    topic: str
    llm_assignments: Dict[str, str]  # {role: model_id}
    format: Optional[str] = 'us_parliamentary'
    language: Optional[str] = 'zh'


class JoinSessionRequest(BaseModel):
    role: Optional[str] = None  # 'debater', 'judge', 'viewer'
    side: Optional[str] = None  # 'affirmative' or 'negative' (if debater)
    position: Optional[int] = None  # 1 or 2 (if debater)


class SendMessageRequest(BaseModel):
    content: str


class AdvanceStageRequest(BaseModel):
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
        from models.debateverse import DebateParticipant, DebateMessage, DebateSession
        participant = db.query(DebateParticipant).filter_by(id=participant_id).first()
        
        if not participant:
            yield f'data: {json.dumps({"type": "error", "error": "Participant not found"})}\n\n'
            return
        
        model = participant.model_id or 'qwen'
        
        # Stream from LLM service and collect content
        from services.llm_service import llm_service
        
        full_content = ""
        full_thinking = ""
        
        async for chunk in llm_service.chat_stream(
            messages=messages,
            model=model,
            temperature=0.7,
            max_tokens=2000,
            enable_thinking=True,
            yield_structured=True,
            user_id=user_id,
            request_type='debateverse',
            endpoint_path=f'/api/debateverse/sessions/{session_id}/stream'
        ):
            if isinstance(chunk, dict):
                chunk_type = chunk.get('type')
                if chunk_type == 'token':
                    full_content += chunk.get('content', '')
                elif chunk_type == 'thinking':
                    full_thinking += chunk.get('content', '')
                yield f'data: {json.dumps(chunk)}\n\n'
        
        # Save message to database
        session = db.query(DebateSession).filter_by(id=session_id).first()
        if not session:
            yield f'data: {json.dumps({"type": "error", "error": "Session not found"})}\n\n'
            return
        
        round_number = service._get_next_round_number(stage)
        message_type = service._get_message_type_for_stage(stage)
        
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
        
        # Generate TTS audio asynchronously (non-blocking)
        try:
            from services.dashscope_tts import get_tts_service
            from pathlib import Path
            import uuid
            
            tts_service = get_tts_service()
            if tts_service.is_available() and full_content.strip():
                # Generate audio file path
                audio_dir = Path("static/debateverse_audio")
                audio_dir.mkdir(parents=True, exist_ok=True)
                audio_filename = f"{session_id}_{message.id}_{uuid.uuid4().hex[:8]}.mp3"
                audio_path = audio_dir / audio_filename
                
                # Generate TTS audio
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
                    logger.info(f"[DEBATEVERSE] Generated TTS audio for message {message.id}: {message.audio_url}")
                else:
                    db.commit()
                    logger.warning(f"[DEBATEVERSE] TTS generation failed for message {message.id}")
            else:
                db.commit()
        except Exception as tts_error:
            # Don't fail the whole request if TTS fails
            logger.error(f"[DEBATEVERSE] TTS error: {tts_error}", exc_info=True)
            db.commit()
        
        yield f'data: {json.dumps({"type": "done"})}\n\n'
    
    except asyncio.CancelledError:
        logger.info(f"[DEBATEVERSE] Stream cancelled for participant {participant_id}")
        raise
    except Exception as e:
        logger.error(f"[DEBATEVERSE] Streaming error: {e}", exc_info=True)
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
            format=request.format
        )
        
        return {
            "session_id": session.id,
            "topic": session.topic,
            "current_stage": session.current_stage,
            "status": session.status,
            "created_at": session.created_at.isoformat()
        }
    except Exception as e:
        logger.error(f"Error creating debate session: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_optional)
):
    """Get debate session with messages and participants."""
    from models.debateverse import DebateSession, DebateParticipant, DebateMessage
    
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
    current_user = Depends(get_current_user_optional)
):
    """Execute coin toss to determine speaking order."""
    service = DebateVerseService(session_id, db)
    result = service.coin_toss()
    
    return {
        "result": result,
        "message": "affirmative_first" if result == "affirmative_first" else "negative_first"
    }


@router.post("/sessions/{session_id}/advance-stage")
async def advance_stage(
    session_id: str,
    request: AdvanceStageRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_optional)
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
    
    from models.debateverse import DebateSession, DebateParticipant, DebateMessage
    
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
    round_number = service._get_next_round_number(current_stage)
    message_type = service._get_message_type_for_stage(current_stage)
    
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
    
    logger.info(f"User {current_user.id} sent message in session {session_id}")
    
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


@router.post("/sessions/{session_id}/next")
async def trigger_next(
    session_id: str,
    language: str = Query('zh'),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_optional)
):
    """
    Trigger next conversation in debate.
    Returns next speaker info for immediate streaming, or indicates stage completion.
    """
    from models.debateverse import DebateSession
    service = DebateVerseService(session_id, db)
    
    session = db.query(DebateSession).filter_by(id=session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
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
    request: Request = None,
    db: Session = Depends(get_db),
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
    
    from models.debateverse import DebateSession
    
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
