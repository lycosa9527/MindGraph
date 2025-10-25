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
from sqlalchemy.orm import Session

from services.client_manager import client_manager
from services.llm_service import llm_service  # LLM Middleware
from services.voice_intent_service import VoiceIntentService
from services.voice_diagram_agent_v2 import voice_diagram_agent_v2
from config.database import get_db
from utils.auth import decode_access_token
from models.auth import User

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


def build_greeting_message(diagram_type: str = 'unknown', language: str = 'zh') -> str:
    """
    Build personalized greeting message based on diagram type and language.
    
    Args:
        diagram_type: Type of diagram (circle_map, bubble_map, etc.)
        language: Language code ('zh' or 'en')
    
    Returns:
        Greeting message string
    """
    # Chinese greetings
    greetings_zh = {
        'circle_map': '你好！我是你的思维助手。我可以帮你完善圆圈图，探索更多观察和想法。有什么我可以帮你的吗？',
        'bubble_map': '嗨！我来帮你描述事物的特征。告诉我你想添加什么形容词或特点吧！',
        'tree_map': '你好！我可以帮你整理分类。让我们一起把想法分门别类吧！',
        'flow_map': '嗨！我来帮你梳理流程。告诉我每一步的顺序，我会协助你理清思路！',
        'brace_map': '你好！我可以帮你分析整体与部分的关系。让我们一起探索吧！',
        'bridge_map': '嗨！我来帮你找出事物之间的类比关系。准备好了吗？',
        'double_bubble_map': '你好！我可以帮你比较两个事物。告诉我它们的相同点和不同点吧！',
        'multi_flow_map': '嗨！我来帮你分析因果关系。让我们一起找出原因和结果！',
        'mind_map': '你好！我是你的思维导图助手。告诉我你的主题，我会帮你展开更多想法！',
        'concept_map': '嗨！我来帮你理清概念之间的关系。让我们一起建立知识网络吧！',
        'default': '你好！我是你的AI助手，很高兴为你服务。你可以问我任何关于思维图的问题，或者让我帮你更新图表内容。'
    }
    
    # English greetings
    greetings_en = {
        'circle_map': 'Hi! I\'m your thinking assistant. I can help you enhance your Circle Map with more observations and ideas. How can I help?',
        'bubble_map': 'Hello! I\'m here to help you describe things. Tell me what adjectives or characteristics you want to add!',
        'tree_map': 'Hi! I can help you organize by categories. Let\'s classify your ideas together!',
        'flow_map': 'Hello! I\'m here to help you map processes. Tell me the sequence, and I\'ll help you clarify!',
        'brace_map': 'Hi! I can help you analyze whole-part relationships. Let\'s explore together!',
        'bridge_map': 'Hello! I\'m here to help you find analogies. Ready to compare?',
        'double_bubble_map': 'Hi! I can help you compare two things. Tell me their similarities and differences!',
        'multi_flow_map': 'Hello! I\'m here to help you analyze cause and effect. Let\'s find the reasons and results!',
        'mind_map': 'Hi! I\'m your mind map assistant. Tell me your topic, and I\'ll help you brainstorm ideas!',
        'concept_map': 'Hello! I\'m here to help you connect concepts. Let\'s build a knowledge network together!',
        'default': 'Hello! I\'m your AI assistant, happy to help. Ask me anything about your diagram, or let me help you update it.'
    }
    
    greetings = greetings_zh if language == 'zh' else greetings_en
    return greetings.get(diagram_type, greetings['default'])


@router.websocket("/ws/voice/{diagram_session_id}")
async def voice_conversation(
    websocket: WebSocket,
    diagram_session_id: str,
    db: Session = Depends(get_db)
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
    # Accept connection first
    await websocket.accept()
    
    # Authenticate AFTER accepting
    try:
        # Get token from query params or cookies
        token = websocket.query_params.get('token')
        if not token:  # Handles both None and '' (empty string)
            token = websocket.cookies.get('access_token')
        
        if not token:
            await websocket.close(code=4001, reason="No authentication token")
            logger.warning("WebSocket auth failed: No token provided")
            return
        
        # Decode and validate token
        payload = decode_access_token(token)
        user_id_str = payload.get("sub")
        
        if not user_id_str:
            await websocket.close(code=4001, reason="Invalid token payload")
            logger.warning("WebSocket auth failed: Invalid token payload")
            return
        
        # Get user from database
        current_user = db.query(User).filter(User.id == int(user_id_str)).first()
        
        if not current_user:
            await websocket.close(code=4001, reason="User not found")
            logger.warning(f"WebSocket auth failed: User {user_id_str} not found")
            return
        
        logger.info(f"WebSocket authenticated: user {current_user.id}")
        
    except Exception as e:
        logger.error(f"WebSocket auth error: {e}", exc_info=True)
        await websocket.close(code=4001, reason=f"Authentication failed: {str(e)}")
        return
    
    voice_session_id = None
    omni_generator = None
    user_id = str(current_user.id)
    
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
        
        # Wait for SDK to initialize conversation (check via async iteration start)
        # The first event will confirm conversation is ready
        logger.debug(f"Waiting for Omni session to initialize...")
        
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
                        if audio_data:
                            # Log every 20th audio packet to avoid spam
                            import random
                            if random.random() < 0.05:
                                logger.debug(f"Forwarding audio to Omni: {len(audio_data)} bytes (base64)")
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
            greeting_sent = False  # Track if greeting was sent
            try:
                async for event in omni_generator:
                    event_type = event.get('type')
                    
                    # Send short greeting when session is ready
                    if not greeting_sent and event_type == 'session_ready':
                        # Build short, personalized greeting (avoid long intro that triggers Omni's self-intro)
                        diagram_type = voice_sessions[voice_session_id].get('diagram_type', 'unknown')
                        greeting = build_greeting_message(diagram_type, language='zh')
                        
                        client_manager.omni_client.create_greeting(
                            greeting_text=greeting
                        )
                        greeting_sent = True
                        logger.info(f"Greeting sent: {greeting[:50]}...")
                    
                    if event_type == 'transcription':
                        transcription_text = event.get('text', '')
                        
                        logger.info(f"Omni transcription: '{transcription_text}'")
                        
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
                        
                        # Parse voice command using simple LangChain agent
                        try:
                            session_context = voice_sessions[voice_session_id].get('context', {})
                            
                            # Use V2 diagram agent to parse command (with full capabilities)
                            command = await voice_diagram_agent_v2.parse_voice_command(
                                transcription_text,
                                session_context
                            )
                            
                            action = command['action']
                            target = command.get('target')
                            node_index = command.get('node_index')
                            confidence = command.get('confidence', 0.0)
                            
                            logger.info(f"Voice command: action={action}, target={target}, node_index={node_index}, confidence={confidence}")
                            
                            # Only proceed if confidence is high enough (except for UI actions)
                            ui_actions = [
                                'open_thinkguide', 'close_thinkguide', 
                                'open_node_palette', 'close_node_palette',
                                'open_mindmate', 'close_mindmate', 'close_all_panels',
                                'select_node', 'explain_node', 
                                'ask_thinkguide', 'ask_mindmate', 'auto_complete', 'help'
                            ]
                            if action not in ui_actions and confidence < 0.7:
                                logger.info(f"Low confidence ({confidence}), skipping diagram update")
                                continue
                            
                            # Handle UI actions first
                            # Panel control
                            if action == 'open_thinkguide':
                                logger.info("Opening ThinkGuide panel")
                                await websocket.send_json({
                                    'type': 'action',
                                    'action': 'open_thinkguide',
                                    'params': {}
                                })
                                continue
                            
                            elif action == 'close_thinkguide':
                                logger.info("Closing ThinkGuide panel")
                                await websocket.send_json({
                                    'type': 'action',
                                    'action': 'close_thinkguide',
                                    'params': {}
                                })
                                continue
                            
                            elif action == 'open_node_palette':
                                logger.info("Opening Node Palette")
                                await websocket.send_json({
                                    'type': 'action',
                                    'action': 'open_node_palette',
                                    'params': {}
                                })
                                continue
                            
                            elif action == 'close_node_palette':
                                logger.info("Closing Node Palette")
                                await websocket.send_json({
                                    'type': 'action',
                                    'action': 'close_node_palette',
                                    'params': {}
                                })
                                continue
                            
                            elif action == 'open_mindmate':
                                logger.info("Opening MindMate AI panel")
                                await websocket.send_json({
                                    'type': 'action',
                                    'action': 'open_mindmate',
                                    'params': {}
                                })
                                continue
                            
                            elif action == 'close_mindmate':
                                logger.info("Closing MindMate AI panel")
                                await websocket.send_json({
                                    'type': 'action',
                                    'action': 'close_mindmate',
                                    'params': {}
                                })
                                continue
                            
                            elif action == 'close_all_panels':
                                logger.info("Closing all panels")
                                await websocket.send_json({
                                    'type': 'action',
                                    'action': 'close_all_panels',
                                    'params': {}
                                })
                                continue
                            
                            # Interaction control
                            elif action == 'auto_complete':
                                logger.info("Triggering AI auto-complete")
                                await websocket.send_json({
                                    'type': 'action',
                                    'action': 'auto_complete',
                                    'params': {}
                                })
                                continue
                            
                            elif action == 'ask_thinkguide' and target:
                                logger.info(f"Sending question to ThinkGuide: {target}")
                                await websocket.send_json({
                                    'type': 'action',
                                    'action': 'ask_thinkguide',
                                    'params': {'message': target}
                                })
                                continue
                            
                            elif action == 'ask_mindmate' and target:
                                logger.info(f"Sending question to MindMate: {target}")
                                await websocket.send_json({
                                    'type': 'action',
                                    'action': 'ask_mindmate',
                                    'params': {'message': target}
                                })
                                continue
                            
                            elif action == 'select_node':
                                node_id = command.get('node_id')
                                if node_id or node_index is not None:
                                    # Resolve node_id from index if needed
                                    resolved_node_id = node_id
                                    if node_index is not None and not resolved_node_id:
                                        nodes = session_context.get('diagram_data', {}).get('children', [])
                                        if 0 <= node_index < len(nodes):
                                            node = nodes[node_index]
                                            resolved_node_id = node.get('id') if isinstance(node, dict) else f"context_{node_index}"
                                    
                                    if resolved_node_id:
                                        logger.info(f"Selecting node: {resolved_node_id}")
                                        await websocket.send_json({
                                            'type': 'action',
                                            'action': 'select_node',
                                            'params': {'node_id': resolved_node_id}
                                        })
                                continue
                            
                            elif action == 'explain_node':
                                node_id = command.get('node_id')
                                node_label = target  # The text to explain
                                if (node_id or node_index is not None) and node_label:
                                    # Resolve node_id from index if needed
                                    resolved_node_id = node_id
                                    if node_index is not None and not resolved_node_id:
                                        nodes = session_context.get('diagram_data', {}).get('children', [])
                                        if 0 <= node_index < len(nodes):
                                            node = nodes[node_index]
                                            resolved_node_id = node.get('id') if isinstance(node, dict) else f"context_{node_index}"
                                            if not node_label:
                                                node_label = node.get('text', node.get('label', ''))
                                    
                                    if resolved_node_id and node_label:
                                        logger.info(f"Explaining node: {resolved_node_id} ({node_label})")
                                        await websocket.send_json({
                                            'type': 'action',
                                            'action': 'explain_node',
                                            'params': {
                                                'node_id': resolved_node_id,
                                                'node_label': node_label,
                                                'prompt': f'请解释一下"{node_label}"这个概念，用简单的语言，适合K12学生理解。'
                                            }
                                        })
                                continue
                            
                            elif action in ['help', 'none']:
                                # Not a diagram update - just conversation or help request
                                if action == 'help':
                                    # Open ThinkGuide for help
                                    logger.info("User requested help - opening ThinkGuide")
                                    await websocket.send_json({
                                        'type': 'action',
                                        'action': 'open_thinkguide',
                                        'params': {}
                                    })
                                else:
                                    logger.debug("No diagram update needed - general conversation")
                                continue
                            
                            # Handle diagram updates
                            if action == 'update_center' and target:
                                logger.info(f"Updating center to: {target}")
                                
                                await websocket.send_json({
                                    'type': 'diagram_update',
                                    'action': 'update_center',
                                    'updates': {'new_text': target}
                                })
                                
                                # Update session context
                                if 'diagram_data' not in session_context:
                                    session_context['diagram_data'] = {}
                                if 'center' not in session_context['diagram_data']:
                                    session_context['diagram_data']['center'] = {}
                                session_context['diagram_data']['center']['text'] = target
                            
                            elif action == 'update_node' and target and node_index is not None:
                                logger.info(f"Updating node {node_index} to: {target}")
                                
                                # Get node ID from index
                                nodes = session_context.get('diagram_data', {}).get('children', [])
                                if 0 <= node_index < len(nodes):
                                    node = nodes[node_index]
                                    node_id = node.get('id') if isinstance(node, dict) else f"context_{node_index}"
                                    
                                    await websocket.send_json({
                                        'type': 'diagram_update',
                                        'action': 'update_nodes',
                                        'updates': [{
                                            'node_id': node_id,
                                            'new_text': target
                                        }]
                                    })
                            
                            elif action == 'add_node' and target:
                                logger.info(f"Adding node: {target}")
                                
                                await websocket.send_json({
                                    'type': 'diagram_update',
                                    'action': 'add_nodes',
                                    'updates': [{'text': target}]
                                })
                            
                            elif action == 'delete_node' and node_index is not None:
                                logger.info(f"Deleting node: {node_index}")
                                
                                nodes = session_context.get('diagram_data', {}).get('children', [])
                                if 0 <= node_index < len(nodes):
                                    node = nodes[node_index]
                                    node_id = node.get('id') if isinstance(node, dict) else f"context_{node_index}"
                                    
                                    await websocket.send_json({
                                        'type': 'diagram_update',
                                        'action': 'remove_nodes',
                                        'updates': [node_id]
                                    })
                            
                            elif action == 'none':
                                # Not a diagram update - just conversation
                                logger.debug("No diagram update needed - general conversation")
                        
                        except Exception as voice_error:
                            logger.error(f"Voice command processing error: {voice_error}", exc_info=True)
                    
                    elif event_type == 'text_chunk':
                        text_chunk = event.get('text', '')
                        logger.debug(f"Omni text chunk: '{text_chunk}'")
                        await websocket.send_json({
                            'type': 'text_chunk',
                            'text': text_chunk
                        })
                    
                    elif event_type == 'audio_chunk':
                        # Send base64 audio to client
                        audio_bytes = event.get('audio')
                        audio_b64 = base64.b64encode(audio_bytes).decode('ascii')
                        
                        # Log audio chunk (every 5th to avoid spam)
                        import random
                        if random.random() < 0.2:
                            logger.debug(f"Omni audio chunk: {len(audio_bytes)} bytes -> {len(audio_b64)} base64")
                        
                        await websocket.send_json({
                            'type': 'audio_chunk',
                            'audio': audio_b64
                        })
                    
                    elif event_type == 'speech_started':
                        logger.info(f"VAD: Speech started at {event.get('audio_start_ms')}ms")
                        await websocket.send_json({
                            'type': 'speech_started',
                            'audio_start_ms': event.get('audio_start_ms')
                        })
                    
                    elif event_type == 'speech_stopped':
                        logger.info(f"VAD: Speech stopped at {event.get('audio_end_ms')}ms")
                        await websocket.send_json({
                            'type': 'speech_stopped',
                            'audio_end_ms': event.get('audio_end_ms')
                        })
                    
                    elif event_type == 'response_done':
                        logger.info(f"Omni response complete")
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

