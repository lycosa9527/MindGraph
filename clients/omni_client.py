"""
Qwen Omni Client - WebSocket Implementation
===========================================

Native WebSocket implementation for Omni Realtime API.
Uses direct WebSocket connection (no SDK dependency) for:
- Full control over connection lifecycle
- Direct middleware integration
- Better transparency and debugging
- No SDK limitations
- Fully async (no threading needed!)

@author lycosa9527
@made_by MindSpring Team
"""

import asyncio
import json
import base64
import time
import logging
from typing import Optional, Callable, Dict, Any, AsyncGenerator
from enum import Enum

import websockets
from websockets.exceptions import ConnectionClosed

from config.settings import config

logger = logging.getLogger('OMNI')


class TurnDetectionMode(Enum):
    SERVER_VAD = "server_vad"
    MANUAL = "manual"


class OmniRealtimeClient:
    """
    Native WebSocket client for DashScope Omni Realtime API.
    
    Provides full control over WebSocket connection and event handling.
    Integrates directly with middleware for rate limiting, error handling, etc.
    """
    
    # Omni Realtime API WebSocket URL
    # Format: wss://dashscope.aliyuncs.com/api-ws/v1/realtime?model={model}
    BASE_URL = "wss://dashscope.aliyuncs.com/api-ws/v1/realtime"
    
    def __init__(
        self,
        api_key: str,
        model: str = "qwen3-omni-flash-realtime-2025-12-01",
        voice: str = "Cherry",
        instructions: str = "You are a helpful assistant.",
        turn_detection_mode: TurnDetectionMode = TurnDetectionMode.SERVER_VAD,
        vad_threshold: float = 0.5,
        vad_silence_ms: int = 1200,
        vad_prefix_ms: int = 300,
        input_format: str = "pcm16",
        output_format: str = "pcm24",
        transcription_model: str = "gummy-realtime-v1",
        # Event handlers
        on_transcription: Optional[Callable[[str], None]] = None,
        on_text_chunk: Optional[Callable[[str], None]] = None,
        on_audio_chunk: Optional[Callable[[bytes], None]] = None,
        on_response_done: Optional[Callable[[dict], None]] = None,
        on_speech_started: Optional[Callable[[int, str], None]] = None,
        on_speech_stopped: Optional[Callable[[int, str], None]] = None,
        on_error: Optional[Callable[[dict], None]] = None,
        # Additional event handlers
        on_session_created: Optional[Callable[[dict], None]] = None,
        on_session_updated: Optional[Callable[[dict], None]] = None,
        on_response_created: Optional[Callable[[dict], None]] = None,
        on_audio_buffer_committed: Optional[Callable[[str], None]] = None,
        on_audio_buffer_cleared: Optional[Callable[[], None]] = None,
        on_item_created: Optional[Callable[[dict], None]] = None,
        on_response_text_done: Optional[Callable[[str], None]] = None,
        on_response_audio_done: Optional[Callable[[], None]] = None,
        on_response_audio_transcript_done: Optional[Callable[[str], None]] = None,
        on_output_item_added: Optional[Callable[[dict], None]] = None,
        on_output_item_done: Optional[Callable[[dict], None]] = None,
        on_content_part_added: Optional[Callable[[dict], None]] = None,
        on_content_part_done: Optional[Callable[[dict], None]] = None,
    ):
        self.api_key = api_key
        self.model = model
        self.voice = voice
        self.instructions = instructions
        self.turn_detection_mode = turn_detection_mode
        self.vad_threshold = vad_threshold
        self.vad_silence_ms = vad_silence_ms
        self.vad_prefix_ms = vad_prefix_ms
        self.input_format = input_format
        self.output_format = output_format
        self.transcription_model = transcription_model
        
        # WebSocket connection
        self.ws = None
        self._connected = False
        self._message_handler_task = None
        
        # Event handlers
        self.on_transcription = on_transcription
        self.on_text_chunk = on_text_chunk
        self.on_audio_chunk = on_audio_chunk
        self.on_response_done = on_response_done
        self.on_speech_started = on_speech_started
        self.on_speech_stopped = on_speech_stopped
        self.on_error = on_error
        self.on_session_created = on_session_created
        self.on_session_updated = on_session_updated
        self.on_response_created = on_response_created
        self.on_audio_buffer_committed = on_audio_buffer_committed
        self.on_audio_buffer_cleared = on_audio_buffer_cleared
        self.on_item_created = on_item_created
        self.on_response_text_done = on_response_text_done
        self.on_response_audio_done = on_response_audio_done
        self.on_response_audio_transcript_done = on_response_audio_transcript_done
        self.on_output_item_added = on_output_item_added
        self.on_output_item_done = on_output_item_done
        self.on_content_part_added = on_content_part_added
        self.on_content_part_done = on_content_part_done
        
        # Response tracking
        self._current_response_id = None
        self._current_item_id = None
        self._is_responding = False
        
        # Session tracking
        self.session_id = None
        
        logger.debug(f"Initialized: model={model}, voice={voice}, vad_threshold={vad_threshold}")
    
    async def connect(self) -> None:
        """Connect to Omni Realtime API via WebSocket."""
        if self._connected:
            logger.warning("Already connected")
            return
        
        url = f"{self.BASE_URL}?model={self.model}"
        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }
        
        try:
            self.ws = await websockets.connect(url, additional_headers=headers)
            self._connected = True
            logger.debug("WebSocket connected to Omni API")
            
            # Configure session
            await self._configure_session()
            
            # Start message handler
            self._message_handler_task = asyncio.create_task(self._handle_messages())
            
        except Exception as e:
            self._connected = False
            logger.error(f"Failed to connect: {e}", exc_info=True)
            raise
    
    async def _configure_session(self) -> None:
        """Configure session with initial settings."""
        session_config = {
            "modalities": ["text", "audio"],
            "voice": self.voice,
            "instructions": self.instructions,
            "input_audio_format": self.input_format,
            "output_audio_format": self.output_format,
            "input_audio_transcription": {
                "model": self.transcription_model
            }
        }
        
        if self.turn_detection_mode == TurnDetectionMode.SERVER_VAD:
            session_config['turn_detection'] = {
                "type": "server_vad",
                "threshold": self.vad_threshold,
                "prefix_padding_ms": self.vad_prefix_ms,
                "silence_duration_ms": self.vad_silence_ms
            }
        elif self.turn_detection_mode == TurnDetectionMode.MANUAL:
            session_config['turn_detection'] = None
        
        await self.update_session(session_config)
    
    async def _send_event(self, event: Dict[str, Any]) -> None:
        """Send event to Omni API."""
        if not self._connected or not self.ws:
            raise ConnectionError("Not connected to Omni API")
        
        event['event_id'] = f"event_{int(time.time() * 1000)}"
        await self.ws.send(json.dumps(event))
        logger.debug(f"Sent event: {event.get('type')}")
    
    async def update_session(self, config: Dict[str, Any]) -> None:
        """Update session configuration."""
        event = {
            "type": "session.update",
            "session": config
        }
        await self._send_event(event)
    
    async def append_audio(self, audio_base64: str) -> None:
        """Append audio chunk to input buffer."""
        event = {
            "type": "input_audio_buffer.append",
            "audio": audio_base64
        }
        await self._send_event(event)
    
    async def commit_audio_buffer(self) -> None:
        """Commit audio buffer to trigger processing."""
        event = {
            "type": "input_audio_buffer.commit"
        }
        await self._send_event(event)
    
    async def clear_audio_buffer(self) -> None:
        """Clear audio buffer."""
        event = {
            "type": "input_audio_buffer.clear"
        }
        await self._send_event(event)
    
    async def create_response(self, instructions: Optional[str] = None) -> None:
        """Create a response (for manual mode or text messages)."""
        event = {
            "type": "response.create"
        }
        if instructions:
            # For text messages, we can include instructions
            event["instructions"] = instructions
        await self._send_event(event)
    
    async def cancel_response(self) -> None:
        """Cancel current response."""
        event = {
            "type": "response.cancel"
        }
        await self._send_event(event)
    
    async def append_image(self, image_bytes: bytes, format: str = "jpeg") -> None:
        """Append image to input buffer."""
        image_b64 = base64.b64encode(image_bytes).decode('ascii')
        event = {
            "type": "input_image_buffer.append",
            "image": image_b64,
            "format": format
        }
        await self._send_event(event)
    
    async def _handle_interruption(self) -> None:
        """Handle user interruption of current response."""
        if not self._is_responding:
            return
        
        if self._current_response_id:
            await self.cancel_response()
        
        self._is_responding = False
        self._current_response_id = None
        self._current_item_id = None
    
    async def _handle_messages(self) -> None:
        """Handle incoming messages from Omni API."""
        try:
            async for message in self.ws:
                try:
                    event = json.loads(message)
                    await self._process_event(event)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse message: {e}")
                    if self.on_error:
                        self.on_error({'type': 'parse_error', 'message': str(e)})
                except Exception as e:
                    logger.error(f"Error processing event: {e}", exc_info=True)
                    if self.on_error:
                        self.on_error({'type': 'processing_error', 'message': str(e)})
        
        except ConnectionClosed:
            logger.debug("WebSocket connection closed")
            self._connected = False
        except Exception as e:
            logger.error(f"Error in message handler: {e}", exc_info=True)
            self._connected = False
            if self.on_error:
                self.on_error({'type': 'connection_error', 'message': str(e)})
    
    async def _process_event(self, event: Dict[str, Any]) -> None:
        """Process a single event from Omni API."""
        event_type = event.get('type')
        
        try:
            # Session Events
            if event_type == 'session.created':
                self.session_id = event.get('session', {}).get('id')
                logger.debug(f"Session created: {self.session_id}")
                if self.on_session_created:
                    # Callbacks may be sync or async - handle both
                    result = self.on_session_created(event.get('session', {}))
                    if asyncio.iscoroutine(result):
                        await result
            
            elif event_type == 'session.updated':
                session = event.get('session', {})
                logger.debug(f"Session updated: {session.get('id')}")
                if self.on_session_updated:
                    result = self.on_session_updated(session)
                    if asyncio.iscoroutine(result):
                        await result
            
            # Error Events
            elif event_type == 'error':
                error = event.get('error', {})
                logger.error(f"Error: {error.get('type')} - {error.get('message')}")
                if self.on_error:
                    result = self.on_error(error)
                    if asyncio.iscoroutine(result):
                        await result
            
            # Input Audio Buffer Events (VAD)
            elif event_type == 'input_audio_buffer.speech_started':
                audio_start_ms = event.get('audio_start_ms', 0)
                item_id = event.get('item_id', '')
                logger.debug(f"VAD: Speech started at {audio_start_ms}ms (item: {item_id})")
                if self.on_speech_started:
                    result = self.on_speech_started(audio_start_ms, item_id)
                    if asyncio.iscoroutine(result):
                        await result
                
                # Handle interruption
                if self._is_responding:
                    await self._handle_interruption()
            
            elif event_type == 'input_audio_buffer.speech_stopped':
                audio_end_ms = event.get('audio_end_ms', 0)
                item_id = event.get('item_id', '')
                logger.debug(f"VAD: Speech stopped at {audio_end_ms}ms (item: {item_id})")
                if self.on_speech_stopped:
                    result = self.on_speech_stopped(audio_end_ms, item_id)
                    if asyncio.iscoroutine(result):
                        await result
            
            elif event_type == 'input_audio_buffer.committed':
                item_id = event.get('item_id', '')
                logger.debug(f"Audio buffer committed (item: {item_id})")
                if self.on_audio_buffer_committed:
                    result = self.on_audio_buffer_committed(item_id)
                    if asyncio.iscoroutine(result):
                        await result
            
            elif event_type == 'input_audio_buffer.cleared':
                logger.debug("Audio buffer cleared")
                if self.on_audio_buffer_cleared:
                    result = self.on_audio_buffer_cleared()
                    if asyncio.iscoroutine(result):
                        await result
            
            # Conversation Item Events
            elif event_type == 'conversation.item.created':
                item = event.get('item', {})
                logger.debug(f"Item created: {item.get('id')} (role: {item.get('role')})")
                if self.on_item_created:
                    result = self.on_item_created(item)
                    if asyncio.iscoroutine(result):
                        await result
            
            elif event_type == 'conversation.item.input_audio_transcription.completed':
                transcript = event.get('transcript', '')
                item_id = event.get('item_id', '')
                logger.debug(f"Transcription: '{transcript}' (item: {item_id})")
                if self.on_transcription:
                    result = self.on_transcription(transcript)
                    if asyncio.iscoroutine(result):
                        await result
            
            elif event_type == 'conversation.item.input_audio_transcription.failed':
                error = event.get('error', {})
                item_id = event.get('item_id', '')
                logger.error(f"Transcription failed for {item_id}: {error.get('message')}")
                if self.on_error:
                    error_data = {
                        'type': 'transcription_failed',
                        'message': error.get('message', 'Transcription failed'),
                        'item_id': item_id
                    }
                    result = self.on_error(error_data)
                    if asyncio.iscoroutine(result):
                        await result
            
            # Response Events
            elif event_type == 'response.created':
                resp = event.get('response', {})
                self._current_response_id = resp.get('id')
                self._is_responding = True
                logger.debug(f"Response created: {self._current_response_id}")
                if self.on_response_created:
                    result = self.on_response_created(resp)
                    if asyncio.iscoroutine(result):
                        await result
            
            elif event_type == 'response.done':
                resp = event.get('response', {})
                usage = resp.get('usage', {})
                logger.debug(f"Response done (tokens: {usage.get('total_tokens', 0)})")
                self._is_responding = False
                self._current_response_id = None
                self._current_item_id = None
                if self.on_response_done:
                    result = self.on_response_done(resp)
                    if asyncio.iscoroutine(result):
                        await result
            
            # Response Text Events
            elif event_type == 'response.text.delta':
                delta = event.get('delta', '')
                logger.debug(f"Text delta: '{delta}'")
                if self.on_text_chunk:
                    result = self.on_text_chunk(delta)
                    if asyncio.iscoroutine(result):
                        await result
            
            elif event_type == 'response.text.done':
                text = event.get('text', '')
                logger.debug(f"Text done: {text[:50]}...")
                if self.on_response_text_done:
                    result = self.on_response_text_done(text)
                    if asyncio.iscoroutine(result):
                        await result
            
            # Response Audio Events
            elif event_type == 'response.audio.delta':
                audio_base64 = event.get('delta', '')
                try:
                    audio_bytes = base64.b64decode(audio_base64)
                    logger.debug(f"Audio delta: {len(audio_bytes)} bytes")
                    if self.on_audio_chunk:
                        result = self.on_audio_chunk(audio_bytes)
                        if asyncio.iscoroutine(result):
                            await result
                except Exception as e:
                    logger.error(f"Failed to decode audio: {e}")
            
            elif event_type == 'response.audio.done':
                logger.debug("Audio done")
                if self.on_response_audio_done:
                    result = self.on_response_audio_done()
                    if asyncio.iscoroutine(result):
                        await result
            
            # Response Audio Transcript Events
            elif event_type == 'response.audio_transcript.delta':
                delta = event.get('delta', '')
                if self.on_text_chunk:
                    result = self.on_text_chunk(delta)
                    if asyncio.iscoroutine(result):
                        await result
            
            elif event_type == 'response.audio_transcript.done':
                transcript = event.get('transcript', '')
                logger.debug(f"Audio transcript done: {transcript[:50]}...")
                if self.on_response_audio_transcript_done:
                    result = self.on_response_audio_transcript_done(transcript)
                    if asyncio.iscoroutine(result):
                        await result
            
            # Response Output Item Events
            elif event_type == 'response.output_item.added':
                item = event.get('item', {})
                self._current_item_id = item.get('id')
                logger.debug(f"Output item added: {item.get('id')}")
                if self.on_output_item_added:
                    result = self.on_output_item_added(item)
                    if asyncio.iscoroutine(result):
                        await result
            
            elif event_type == 'response.output_item.done':
                item = event.get('item', {})
                logger.debug(f"Output item done: {item.get('id')}")
                if self.on_output_item_done:
                    result = self.on_output_item_done(item)
                    if asyncio.iscoroutine(result):
                        await result
            
            # Response Content Part Events
            elif event_type == 'response.content_part.added':
                part = event.get('part', {})
                logger.debug(f"Content part added: {part.get('type')}")
                if self.on_content_part_added:
                    result = self.on_content_part_added(part)
                    if asyncio.iscoroutine(result):
                        await result
            
            elif event_type == 'response.content_part.done':
                part = event.get('part', {})
                logger.debug(f"Content part done: {part.get('type')}")
                if self.on_content_part_done:
                    result = self.on_content_part_done(part)
                    if asyncio.iscoroutine(result):
                        await result
            
            else:
                logger.debug(f"Unhandled event type: {event_type}")
        
        except Exception as e:
            logger.error(f"Error processing event {event_type}: {e}", exc_info=True)
            if self.on_error:
                self.on_error({'type': 'event_processing_error', 'message': str(e), 'event_type': event_type})
    
    async def close(self) -> None:
        """Close WebSocket connection."""
        self._connected = False
        
        if self._message_handler_task:
            self._message_handler_task.cancel()
            try:
                await self._message_handler_task
            except asyncio.CancelledError:
                pass
        
        if self.ws:
            try:
                await self.ws.close()
            except Exception as e:
                logger.debug(f"Error closing WebSocket: {e}")
            self.ws = None
        
        logger.debug("WebSocket connection closed")
    
    @property
    def conversation(self):
        """Compatibility property for existing code."""
        return self if self._connected else None
    
    def is_connected(self) -> bool:
        """Check if connected."""
        return self._connected


# ============================================================================
# Wrapper Class for Backward Compatibility
# ============================================================================

class OmniClient:
    """
    Wrapper class that matches the existing OmniClient interface.
    Uses native WebSocket implementation internally.
    Maintains backward compatibility with existing code.
    """
    
    def __init__(self):
        """Initialize with config from settings."""
        self.api_key = config.QWEN_API_KEY
        self.model = config.QWEN_OMNI_MODEL
        self.voice = config.QWEN_OMNI_VOICE
        self.vad_threshold = config.QWEN_OMNI_VAD_THRESHOLD
        self.vad_silence_ms = config.QWEN_OMNI_VAD_SILENCE_MS
        self.vad_prefix_ms = config.QWEN_OMNI_VAD_PREFIX_MS
        self.input_format = config.QWEN_OMNI_INPUT_FORMAT
        self.output_format = config.QWEN_OMNI_OUTPUT_FORMAT
        self.transcription_model = config.QWEN_OMNI_TRANSCRIPTION_MODEL
        
        # Native WebSocket client (will be created in start_conversation)
        self._native_client: Optional[OmniRealtimeClient] = None
        self.event_queue: Optional[asyncio.Queue] = None
        
        logger.debug(f"Initialized: model={self.model}, voice={self.voice}, vad_threshold={self.vad_threshold}")
    
    async def start_conversation(
        self,
        instructions: Optional[str] = None,
        on_event: Optional[Callable] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Start voice conversation, yield events.
        
        Args:
            instructions: System prompt for the conversation
            on_event: Callback for each event
        
        Yields:
            Event dictionaries with type and data
        """
        self.event_queue = asyncio.Queue()
        
        # Helper to queue events asynchronously
        async def queue_event(event: Dict[str, Any]):
            """Queue event asynchronously"""
            await self.event_queue.put(event)
        
        # Create native WebSocket client with async-safe event handlers
        self._native_client = OmniRealtimeClient(
            api_key=self.api_key,
            model=self.model,
            voice=self.voice,
            instructions=instructions or "你是一个专业的教育助手，帮助K12教师和学生理解概念。",
            turn_detection_mode=TurnDetectionMode.SERVER_VAD,
            vad_threshold=self.vad_threshold,
            vad_silence_ms=self.vad_silence_ms,
            vad_prefix_ms=self.vad_prefix_ms,
            input_format=self.input_format,
            output_format=self.output_format,
            transcription_model=self.transcription_model,
            # Wire up all event handlers to queue events
            # Callbacks are async coroutines that queue events
            on_transcription=lambda text: queue_event({'type': 'transcription', 'text': text}),
            on_text_chunk=lambda text: queue_event({'type': 'text_chunk', 'text': text}),
            on_audio_chunk=lambda audio: queue_event({'type': 'audio_chunk', 'audio': audio}),
            on_response_done=lambda resp: queue_event({'type': 'response_done', 'response': resp}),
            on_speech_started=lambda ms, item_id: queue_event({
                'type': 'speech_started',
                'audio_start_ms': ms,
                'item_id': item_id
            }),
            on_speech_stopped=lambda ms, item_id: queue_event({
                'type': 'speech_stopped',
                'audio_end_ms': ms,
                'item_id': item_id
            }),
            on_error=lambda error: queue_event({'type': 'error', 'error': error}),
            # Additional event handlers
            on_session_created=lambda session: queue_event({'type': 'session_created', 'session': session}),
            on_session_updated=lambda session: queue_event({'type': 'session_updated', 'session': session}),
            on_response_created=lambda resp: queue_event({'type': 'response_created', 'response': resp}),
            on_audio_buffer_committed=lambda item_id: queue_event({'type': 'audio_buffer_committed', 'item_id': item_id}),
            on_audio_buffer_cleared=lambda: queue_event({'type': 'audio_buffer_cleared'}),
            on_item_created=lambda item: queue_event({'type': 'item_created', 'item': item}),
            on_response_text_done=lambda text: queue_event({'type': 'response_text_done', 'text': text}),
            on_response_audio_done=lambda: queue_event({'type': 'response_audio_done'}),
            on_response_audio_transcript_done=lambda transcript: queue_event({
                'type': 'response_audio_transcript_done',
                'transcript': transcript
            }),
            on_output_item_added=lambda item: queue_event({'type': 'output_item_added', 'item': item}),
            on_output_item_done=lambda item: queue_event({'type': 'output_item_done', 'item': item}),
            on_content_part_added=lambda part: queue_event({'type': 'content_part_added', 'part': part}),
            on_content_part_done=lambda part: queue_event({'type': 'content_part_done', 'part': part})
        )
        
        # Connect
        try:
            await self._native_client.connect()
            # Signal session ready
            await self.event_queue.put({'type': 'session_ready'})
        except Exception as e:
            logger.error(f"Failed to connect: {e}", exc_info=True)
            await self.event_queue.put({'type': 'error', 'error': str(e)})
            return
        
        # Yield events
        try:
            while True:
                event = await self.event_queue.get()
                
                if on_event:
                    on_event(event)
                
                yield event
                
                if event['type'] in ('error', 'conversation_end'):
                    break
        except Exception as e:
            logger.error(f"Event yielding error: {e}", exc_info=True)
            yield {'type': 'error', 'error': str(e)}
        finally:
            if self._native_client:
                await self._native_client.close()
                self._native_client = None
    
    async def send_audio(self, audio_base64: str):
        """Send audio chunk to Omni (base64 encoded PCM)."""
        if not self._native_client or not self._native_client.is_connected():
            logger.warning("No active conversation")
            return
        
        try:
            await self._native_client.append_audio(audio_base64)
        except Exception as e:
            logger.error(f"Failed to send audio: {e}")
    
    async def update_instructions(self, new_instructions: str):
        """
        Update session instructions dynamically.
        CRITICAL: Must preserve ALL session settings when updating!
        """
        if not self._native_client or not self._native_client.is_connected():
            logger.warning("No active conversation to update")
            return
        
        try:
            # Build session config preserving all settings
            session_config = {
                "modalities": ["text", "audio"],
                "voice": self.voice,
                "instructions": new_instructions,
                "input_audio_format": self.input_format,
                "output_audio_format": self.output_format,
                "input_audio_transcription": {
                    "model": self.transcription_model
                },
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": self.vad_threshold,
                    "prefix_padding_ms": self.vad_prefix_ms,
                    "silence_duration_ms": self.vad_silence_ms
                }
            }
            
            await self._native_client.update_session(session_config)
            logger.debug(f"Instructions updated: {new_instructions[:50]}...")
        
        except Exception as e:
            logger.error(f"Failed to update instructions: {e}", exc_info=True)
    
    async def create_greeting(self, greeting_text: str = "Hello! How can I help you today?"):
        """Create an initial greeting response from Omni."""
        if not self._native_client or not self._native_client.is_connected():
            logger.warning("No active conversation for greeting")
            return
        
        try:
            await self._native_client.create_response(instructions=greeting_text)
            logger.debug(f"Greeting created: {greeting_text}")
        except Exception as e:
            logger.error(f"Failed to create greeting: {e}", exc_info=True)
    
    async def send_text_message(self, text: str):
        """Send a text message to Omni and trigger a response."""
        if not self._native_client or not self._native_client.is_connected():
            logger.warning("No active conversation for text message")
            return
        
        try:
            instructions = f"The user typed this message: \"{text}\". Please respond helpfully and naturally."
            await self._native_client.create_response(instructions=instructions)
            logger.debug(f"Text message sent: {text[:50]}...")
        except Exception as e:
            logger.error(f"Failed to send text message: {e}", exc_info=True)
    
    async def cancel_response(self):
        """Cancel an ongoing response from Omni."""
        if not self._native_client or not self._native_client.is_connected():
            logger.warning("No active conversation to cancel response")
            return
        
        try:
            await self._native_client.cancel_response()
            logger.debug("Response cancelled")
        except Exception as e:
            logger.error(f"Failed to cancel response: {e}", exc_info=True)
    
    async def clear_audio_buffer(self):
        """Clear audio buffer."""
        if not self._native_client or not self._native_client.is_connected():
            logger.warning("No active conversation to clear audio buffer")
            return
        
        try:
            await self._native_client.clear_audio_buffer()
            logger.debug("Audio buffer cleared")
        except Exception as e:
            logger.error(f"Failed to clear audio buffer: {e}", exc_info=True)
    
    async def commit_audio_buffer(self):
        """Commit audio buffer."""
        if not self._native_client or not self._native_client.is_connected():
            logger.warning("No active conversation to commit audio buffer")
            return
        
        try:
            await self._native_client.commit_audio_buffer()
            logger.debug("Audio buffer committed")
        except Exception as e:
            logger.error(f"Failed to commit audio buffer: {e}", exc_info=True)
    
    async def append_image(self, image_bytes: bytes, image_format: str = "jpeg"):
        """Append image to input buffer."""
        if not self._native_client or not self._native_client.is_connected():
            logger.warning("No active conversation to append image")
            return
        
        try:
            await self._native_client.append_image(image_bytes, image_format)
            logger.debug(f"Image appended: {len(image_bytes)} bytes ({image_format})")
        except Exception as e:
            logger.error(f"Failed to append image: {e}", exc_info=True)
    
    @property
    def conversation(self):
        """Compatibility property for existing code."""
        return self._native_client if self._native_client and self._native_client.is_connected() else None

