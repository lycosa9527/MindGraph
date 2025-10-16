"""
Voice Router - Real-time Voice Conversation
WebSocket endpoint for VoiceAgent

Integrates with LLM Middleware:
- Uses LLMService for intent classification (Qwen Turbo)
- Uses ClientManager.omni_client for Omni conversation
- Follows same rate limiting, error handling, timeout patterns

@author lycosa9527
@made_by MindSpring Team
"""

import logging
import asyncio
import base64
from typing import Dict, Any, Optional
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from fastapi.responses import JSONResponse

from services.client_manager import client_manager
from services.llm_service import llm_service  # LLM Middleware
from services.voice_intent_service import VoiceIntentService
from services.rate_limiter import rate_limiter  # Rate limiting middleware
from utils.auth import get_current_user_ws

# Configure logger with module name 'VOICE'
logger = logging.getLogger('VOICE')

router = APIRouter()

# In-memory session storage
voice_sessions: Dict[str, Dict[str, Any]] = {}

# Intent service (uses LLMService internally)
intent_service = VoiceIntentService()


def create_voice_session(
    user_id: str,
    diagram_session_id: Optional[str] = None,
    diagram_type: Optional[str] = None,
    active_panel: Optional[str] = None
) -> str:
    """
    Create new voice session (session-bound to diagram session).
    
    VoiceAgent session lifecycle is controlled by:
    1. Black cat click (activation)
    2. Black cat click again (deactivation)
    3. Session manager cleanup (when diagram session ends)
    4. Navigation to gallery (session manager triggers cleanup)
    """
    import uuid
    session_id = f"voice_{uuid.uuid4().hex[:12]}"
    
    voice_sessions[session_id] = {
        'session_id': session_id,
        'user_id': user_id,
        'diagram_session_id': diagram_session_id,
        'diagram_type': diagram_type,
        'active_panel': active_panel or 'thinkguide',
        'created_at': datetime.now(),
        'last_activity': datetime.now(),
        'conversation_history': []
    }
    
    logger.info(f"Session created: {session_id} (linked to diagram={diagram_session_id})")
    return session_id


def get_voice_session(session_id: str) -> Optional[Dict[str, Any]]:
    """Get session"""
    return voice_sessions.get(session_id)


def update_panel_context(session_id: str, active_panel: str) -> None:
    """Update active panel context"""
    if session_id in voice_sessions:
        old_panel = voice_sessions[session_id].get('active_panel', 'unknown')
        voice_sessions[session_id]['active_panel'] = active_panel
        logger.info(f"Panel context updated: {session_id} ({old_panel} -> {active_panel})")


def end_voice_session(session_id: str, reason: str = 'completed') -> None:
    """End and cleanup session"""
    if session_id in voice_sessions:
        logger.info(f"Session ended: {session_id} (reason={reason})")
        del voice_sessions[session_id]


def cleanup_voice_by_diagram_session(diagram_session_id: str) -> bool:
    """
    Cleanup voice session when diagram session ends.
    Called by session manager on session end or navigation to gallery.
    """
    voice_session_id = None
    for sid, session in voice_sessions.items():
        if session.get('diagram_session_id') == diagram_session_id:
            voice_session_id = sid
            break
    
    if voice_session_id:
        logger.info(f"Cleaning up voice session {voice_session_id} (diagram session {diagram_session_id} ended)")
        end_voice_session(voice_session_id, reason='diagram_session_ended')
        return True
    
    return False


def build_voice_instructions(context: Dict[str, Any]) -> str:
    """Build voice instructions from context"""
    diagram_type = context.get('diagram_type', 'unknown')
    active_panel = context.get('active_panel', 'thinkguide')
    conversation_history = context.get('conversation_history', [])
    selected_nodes = context.get('selected_nodes', [])
    
    instructions = f"""You are a helpful K12 classroom AI assistant for MindGraph.

Current Context:
- Diagram type: {diagram_type}
- Active panel: {active_panel}
- Selected nodes: {len(selected_nodes)}

Your role:
1. Answer questions about the diagram and concepts
2. Help students understand relationships between ideas
3. Suggest appropriate nodes for their thinking
4. Explain concepts in simple, age-appropriate language

Guidelines:
- Be concise and clear
- Use simple vocabulary for K12 students
- Reference specific nodes when relevant
- Encourage critical thinking

Recent conversation:
{conversation_history[-3:] if conversation_history else 'None'}

Respond naturally and helpfully."""
    
    return instructions


@router.websocket("/ws/voice/{diagram_session_id}")
async def voice_conversation(
    websocket: WebSocket,
    diagram_session_id: str,
    current_user: dict = Depends(get_current_user_ws)
):
    """
    WebSocket endpoint for real-time voice conversation.
    
    Protocol:
    Client -> Server:
    - {"type": "start", "diagram_type": str, "active_panel": str, "context": {...}}
    - {"type": "audio", "data": str}  # base64 PCM audio
    - {"type": "context_update", "active_panel": str, "context": {...}}
    - {"type": "stop"}
    
    Server -> Client:
    - {"type": "connected", "session_id": str}
    - {"type": "transcription", "text": str}
    - {"type": "text_chunk", "text": str}
    - {"type": "audio_chunk", "audio": str}  # base64
    - {"type": "speech_started", "audio_start_ms": int}
    - {"type": "speech_stopped", "audio_end_ms": int}
    - {"type": "response_done"}
    - {"type": "action", "action": str, "params": {...}}
    - {"type": "error", "error": str}
    """
    await websocket.accept()
    
    voice_session_id = None
    omni_generator = None
    user_id = str(current_user.id) if hasattr(current_user, 'id') else str(current_user.get('user_id', 'unknown'))
    
    try:
        # Wait for start message
        start_msg = await websocket.receive_json()
        
        if start_msg.get('type') != 'start':
            logger.warning(f"Invalid start message type: {start_msg.get('type')}")
            await websocket.send_json({'type': 'error', 'error': 'Expected start message'})
            await websocket.close()
            return
        
        logger.info(f"Starting voice conversation for user {user_id}")
        
        # Create voice session
        voice_session_id = create_voice_session(
            user_id=user_id,
            diagram_session_id=diagram_session_id,
            diagram_type=start_msg.get('diagram_type'),
            active_panel=start_msg.get('active_panel', 'thinkguide')
        )
        
        logger.debug(f"Session created: {voice_session_id}, diagram_type={start_msg.get('diagram_type')}, panel={start_msg.get('active_panel')}")
        
        # Store initial context
        voice_sessions[voice_session_id]['context'] = start_msg.get('context', {})
        
        # Build instructions
        context = {
            'diagram_type': start_msg.get('diagram_type'),
            'active_panel': start_msg.get('active_panel'),
            'conversation_history': [],
            'selected_nodes': start_msg.get('context', {}).get('selected_nodes', [])
        }
        instructions = build_voice_instructions(context)
        
        logger.debug(f"Built instructions for context: {len(instructions)} chars")
        
        # Start Omni conversation
        omni_generator = client_manager.omni_client.start_conversation(
            instructions=instructions
        )
        
        # Send connected confirmation
        await websocket.send_json({
            'type': 'connected',
            'session_id': voice_session_id
        })
        
        logger.info(f"Voice session {voice_session_id} connected")
        
        # Handle messages concurrently
        async def handle_client_messages():
            """Handle messages from client"""
            try:
                while True:
                    message = await websocket.receive_json()
                    msg_type = message.get('type')
                    
                    if msg_type == 'audio':
                        # Forward audio to Omni
                        audio_data = message.get('data')
                        client_manager.omni_client.send_audio(audio_data)
                    
                    elif msg_type == 'context_update':
                        # Update context and instructions
                        active_panel = message.get('active_panel')
                        new_context = message.get('context', {})
                        
                        update_panel_context(voice_session_id, active_panel)
                        voice_sessions[voice_session_id]['context'].update(new_context)
                        
                        # Rebuild and update instructions
                        updated_context = {
                            'diagram_type': voice_sessions[voice_session_id].get('diagram_type'),
                            'active_panel': active_panel,
                            'conversation_history': voice_sessions[voice_session_id].get('conversation_history', []),
                            'selected_nodes': new_context.get('selected_nodes', [])
                        }
                        new_instructions = build_voice_instructions(updated_context)
                        client_manager.omni_client.update_instructions(new_instructions)
                        
                        logger.info(f"Context updated for {voice_session_id}")
                    
                    elif msg_type == 'stop':
                        break
            
            except WebSocketDisconnect:
                logger.info(f"Client disconnected: {voice_session_id}")
            except Exception as e:
                logger.error(f"Client message error: {e}", exc_info=True)
        
        async def handle_omni_events():
            """Handle events from Omni"""
            try:
                async for event in omni_generator:
                    event_type = event.get('type')
                    
                    if event_type == 'transcription':
                        transcription_text = event.get('text', '')
                        
                        # Send transcription to client
                        await websocket.send_json({
                            'type': 'transcription',
                            'text': transcription_text
                        })
                        
                        # Store in conversation history
                        voice_sessions[voice_session_id]['conversation_history'].append({
                            'role': 'user',
                            'content': transcription_text
                        })
                        
                        # Classify intent and send action if needed
                        try:
                            session_context = voice_sessions[voice_session_id].get('context', {})
                            intent_result = await intent_service.classify_intent(
                                transcription_text,
                                session_context
                            )
                            
                            logger.info(f"Intent classified: {intent_result['intent']} -> {intent_result['target']}")
                            
                            # Route to appropriate action based on intent
                            if intent_result['intent'] == 'help_select_nodes':
                                # Open node palette
                                await websocket.send_json({
                                    'type': 'action',
                                    'action': 'open_node_palette',
                                    'params': {}
                                })
                            
                            elif intent_result['intent'] == 'explain_concept':
                                # Check for context-aware explanation
                                selected_nodes = session_context.get('selected_nodes', [])
                                keywords = ['this', 'that', 'selected', 'just selected', 'i just']
                                
                                if selected_nodes and any(kw in transcription_text.lower() for kw in keywords):
                                    node = selected_nodes[0]
                                    await websocket.send_json({
                                        'type': 'action',
                                        'action': 'explain_node',
                                        'params': {
                                            'node_id': node.get('id'),
                                            'node_label': node.get('label'),
                                            'prompt': f"Explain the concept of '{node.get('label')}' in simple terms for K12 students."
                                        }
                                    })
                        
                        except Exception as intent_error:
                            logger.error(f"Intent classification error: {intent_error}", exc_info=True)
                    
                    elif event_type == 'text_chunk':
                        await websocket.send_json({
                            'type': 'text_chunk',
                            'text': event.get('text')
                        })
                    
                    elif event_type == 'audio_chunk':
                        # Send base64 audio to client
                        audio_b64 = base64.b64encode(event.get('audio')).decode('ascii')
                        await websocket.send_json({
                            'type': 'audio_chunk',
                            'audio': audio_b64
                        })
                    
                    elif event_type == 'speech_started':
                        await websocket.send_json({
                            'type': 'speech_started',
                            'audio_start_ms': event.get('audio_start_ms')
                        })
                    
                    elif event_type == 'speech_stopped':
                        await websocket.send_json({
                            'type': 'speech_stopped',
                            'audio_end_ms': event.get('audio_end_ms')
                        })
                    
                    elif event_type == 'response_done':
                        await websocket.send_json({
                            'type': 'response_done'
                        })
                    
                    elif event_type == 'error':
                        await websocket.send_json({
                            'type': 'error',
                            'error': str(event.get('error'))
                        })
            
            except Exception as e:
                logger.error(f"Omni event error: {e}", exc_info=True)
                await websocket.send_json({'type': 'error', 'error': str(e)})
        
        # Run both handlers concurrently
        await asyncio.gather(
            handle_client_messages(),
            handle_omni_events()
        )
    
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {voice_session_id}")
    
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        try:
            await websocket.send_json({'type': 'error', 'error': str(e)})
        except:
            pass
    
    finally:
        # Cleanup
        if voice_session_id:
            end_voice_session(voice_session_id, reason='websocket_closed')
        
        if client_manager.omni_client:
            client_manager.omni_client.close()


@router.post("/api/voice/cleanup/{diagram_session_id}")
async def cleanup_voice_session(diagram_session_id: str):
    """
    Cleanup voice session when diagram session ends.
    Called by session manager on session end or navigation to gallery.
    """
    try:
        cleaned = cleanup_voice_by_diagram_session(diagram_session_id)
        
        if cleaned:
            return {"success": True, "message": f"Voice session cleaned up for diagram {diagram_session_id}"}
        else:
            return {"success": True, "message": "No active voice session found"}
    
    except Exception as e:
        logger.error(f"Cleanup error: {e}", exc_info=True)
        return {"success": False, "error": str(e)}

