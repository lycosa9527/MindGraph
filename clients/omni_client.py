"""
Qwen Omni Client - Real-time Voice Conversation

@author lycosa9527
@made_by MindSpring Team
"""

import asyncio
import base64
import threading
import logging
from typing import Optional, Callable, Dict, Any, AsyncGenerator

import dashscope
from dashscope.audio.qwen_omni import (
    OmniRealtimeConversation,
    OmniRealtimeCallback,
    MultiModality,
    AudioFormat
)

from config.settings import config

# Configure logger with module name 'OMNI'
logger = logging.getLogger('OMNI')


class OmniCallback(OmniRealtimeCallback):
    """Callback for Qwen Omni server-side events"""
    
    def __init__(
        self,
        on_transcription: Optional[Callable[[str], None]] = None,
        on_text_chunk: Optional[Callable[[str], None]] = None,
        on_audio_chunk: Optional[Callable[[bytes], None]] = None,
        on_response_done: Optional[Callable[[dict], None]] = None,
        on_speech_started: Optional[Callable[[int, str], None]] = None,
        on_speech_stopped: Optional[Callable[[int, str], None]] = None,
        on_error: Optional[Callable[[dict], None]] = None
    ):
        super().__init__()
        self.on_transcription = on_transcription
        self.on_text_chunk = on_text_chunk
        self.on_audio_chunk = on_audio_chunk
        self.on_response_done = on_response_done
        self.on_speech_started = on_speech_started
        self.on_speech_stopped = on_speech_stopped
        self.on_error = on_error
        self.session_id = None
    
    def on_open(self) -> None:
        """Connection opened"""
        logger.info("Connection opened")
    
    def on_close(self, close_status_code: int, close_msg: str) -> None:
        """Connection closed"""
        logger.info(f"Connection closed: {close_status_code} - {close_msg}")
    
    def on_event(self, response: dict) -> None:
        """Handle all Omni server-side events"""
        try:
            event_type = response.get('type')
            event_id = response.get('event_id', '')
            
            # Session Events
            if event_type == 'session.created':
                self.session_id = response.get('session', {}).get('id')
                logger.info(f"Session created: {self.session_id}")
            
            elif event_type == 'session.updated':
                session = response.get('session', {})
                logger.debug(f"Session updated: {session.get('id')}")
            
            # Error Events
            elif event_type == 'error':
                error = response.get('error', {})
                logger.error(f"Error: {error.get('type')} - {error.get('message')}")
                if self.on_error:
                    self.on_error(error)
            
            # Input Audio Buffer Events (VAD)
            elif event_type == 'input_audio_buffer.speech_started':
                audio_start_ms = response.get('audio_start_ms', 0)
                item_id = response.get('item_id', '')
                logger.info(f"[SDK] VAD: Speech started at {audio_start_ms}ms (item: {item_id})")
                if self.on_speech_started:
                    self.on_speech_started(audio_start_ms, item_id)
            
            elif event_type == 'input_audio_buffer.speech_stopped':
                audio_end_ms = response.get('audio_end_ms', 0)
                item_id = response.get('item_id', '')
                logger.info(f"[SDK] VAD: Speech stopped at {audio_end_ms}ms (item: {item_id})")
                if self.on_speech_stopped:
                    self.on_speech_stopped(audio_end_ms, item_id)
            
            elif event_type == 'input_audio_buffer.committed':
                item_id = response.get('item_id', '')
                logger.debug(f"Audio buffer committed (item: {item_id})")
            
            elif event_type == 'input_audio_buffer.cleared':
                logger.debug("Audio buffer cleared")
            
            # Conversation Item Events
            elif event_type == 'conversation.item.created':
                item = response.get('item', {})
                logger.debug(f"Item created: {item.get('id')} (role: {item.get('role')})")
            
            elif event_type == 'conversation.item.input_audio_transcription.completed':
                transcript = response.get('transcript', '')
                item_id = response.get('item_id', '')
                logger.info(f"[SDK] Transcription: '{transcript}' (item: {item_id})")
                if self.on_transcription:
                    self.on_transcription(transcript)
            
            elif event_type == 'conversation.item.input_audio_transcription.failed':
                error = response.get('error', {})
                item_id = response.get('item_id', '')
                logger.error(f"Transcription failed for {item_id}: {error.get('message')}")
            
            # Response Events
            elif event_type == 'response.created':
                resp = response.get('response', {})
                logger.debug(f"Response created: {resp.get('id')}")
            
            elif event_type == 'response.done':
                resp = response.get('response', {})
                usage = resp.get('usage', {})
                logger.info(f"Response done (tokens: {usage.get('total_tokens', 0)})")
                if self.on_response_done:
                    self.on_response_done(resp)
            
            # Response Text Events
            elif event_type == 'response.text.delta':
                delta = response.get('delta', '')
                logger.debug(f"[SDK] Text delta: '{delta}'")
                if self.on_text_chunk:
                    self.on_text_chunk(delta)
            
            elif event_type == 'response.text.done':
                text = response.get('text', '')
                logger.debug(f"[SDK] Text done: {text[:50]}...")
            
            # Response Audio Events
            elif event_type == 'response.audio.delta':
                audio_base64 = response.get('delta', '')
                audio_bytes = base64.b64decode(audio_base64)
                logger.debug(f"[SDK] Audio delta: {len(audio_bytes)} bytes (PCM24)")
                if self.on_audio_chunk:
                    self.on_audio_chunk(audio_bytes)
            
            elif event_type == 'response.audio.done':
                logger.debug("[SDK] Audio done")
            
            # Response Audio Transcript Events
            elif event_type == 'response.audio_transcript.delta':
                delta = response.get('delta', '')
                if self.on_text_chunk:
                    self.on_text_chunk(delta)
            
            elif event_type == 'response.audio_transcript.done':
                transcript = response.get('transcript', '')
                logger.debug(f"Audio transcript: {transcript[:50]}...")
            
            # Response Output Item Events
            elif event_type == 'response.output_item.added':
                item = response.get('item', {})
                logger.debug(f"Output item added: {item.get('id')}")
            
            elif event_type == 'response.output_item.done':
                item = response.get('item', {})
                logger.debug(f"Output item done: {item.get('id')}")
            
            # Response Content Part Events
            elif event_type == 'response.content_part.added':
                part = response.get('part', {})
                logger.debug(f"Content part added: {part.get('type')}")
            
            elif event_type == 'response.content_part.done':
                part = response.get('part', {})
                logger.debug(f"Content part done: {part.get('type')}")
        
        except Exception as e:
            logger.error(f"Event handling error: {e}", exc_info=True)


class OmniClient:
    """Qwen Omni Client - Real-time Voice Conversation"""
    
    def __init__(self):
        """Initialize with config from settings"""
        self.api_key = config.QWEN_API_KEY
        self.model = config.QWEN_OMNI_MODEL
        self.voice = config.QWEN_OMNI_VOICE
        self.vad_threshold = config.QWEN_OMNI_VAD_THRESHOLD
        self.vad_silence_ms = config.QWEN_OMNI_VAD_SILENCE_MS
        self.vad_prefix_ms = config.QWEN_OMNI_VAD_PREFIX_MS
        self.smooth_output = config.QWEN_OMNI_SMOOTH_OUTPUT
        self.input_format = config.QWEN_OMNI_INPUT_FORMAT
        self.output_format = config.QWEN_OMNI_OUTPUT_FORMAT
        self.transcription_model = config.QWEN_OMNI_TRANSCRIPTION_MODEL
        
        dashscope.api_key = self.api_key
        
        self.conversation = None
        self.event_queue = None
        
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
        
        # Capture the event loop BEFORE starting SDK thread
        loop = asyncio.get_running_loop()
        
        def queue_event(event: Dict[str, Any]):
            """Thread-safe event queueing from SDK thread to asyncio"""
            try:
                # Use the captured loop from the async context
                asyncio.run_coroutine_threadsafe(
                    self.event_queue.put(event),
                    loop
                )
            except Exception as e:
                logger.error(f"Failed to queue event: {e}")
        
        # Create callback
        callback = OmniCallback(
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
            on_error=lambda error: queue_event({'type': 'error', 'error': error})
        )
        
        # Start conversation in background thread
        def run_conversation():
            try:
                # Create conversation
                self.conversation = OmniRealtimeConversation(
                    model=self.model,
                    callback=callback
                )
                
                # Connect
                self.conversation.connect()
                
                # Map format strings to enums
                input_format = (
                    AudioFormat.PCM_16000HZ_MONO_16BIT if self.input_format == 'pcm16'
                    else AudioFormat.PCM_24000HZ_MONO_16BIT
                )
                output_format = (
                    AudioFormat.PCM_24000HZ_MONO_16BIT if self.output_format == 'pcm24'
                    else AudioFormat.PCM_16000HZ_MONO_16BIT
                )
                
                # Update session using official SDK pattern
                # VAD mode: Server automatically creates/interrupts responses
                self.conversation.update_session(
                    output_modalities=[MultiModality.TEXT, MultiModality.AUDIO],
                    voice=self.voice,
                    input_audio_format=input_format,
                    output_audio_format=output_format,
                    enable_input_audio_transcription=True,
                    input_audio_transcription_model=self.transcription_model,
                    enable_turn_detection=True,
                    turn_detection_type='server_vad',
                    # Note: VAD parameters are optional, SDK uses smart defaults
                    # Only override if needed for custom behavior
                    prefix_padding_ms=self.vad_prefix_ms,
                    turn_detection_threshold=self.vad_threshold,
                    turn_detection_silence_duration_ms=self.vad_silence_ms,
                    instructions=instructions or "你是一个专业的教育助手，帮助K12教师和学生理解概念。"
                )
                
                logger.info("Session started")
                
                # Signal that session is ready
                queue_event({'type': 'session_ready'})
                
                # Keep thread alive
                self.conversation.thread.join()
            
            except Exception as e:
                logger.error(f"Conversation error: {e}", exc_info=True)
                queue_event({'type': 'error', 'error': str(e)})
        
        # Start thread
        conversation_thread = threading.Thread(target=run_conversation, daemon=True)
        conversation_thread.start()
        
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
    
    def send_audio(self, audio_base64: str):
        """Send audio chunk to Omni (base64 encoded PCM)"""
        if not self.conversation:
            logger.warning("No active conversation")
            return
        
        try:
            self.conversation.append_audio(audio_base64)
        except Exception as e:
            logger.error(f"Failed to send audio: {e}")
    
    def update_instructions(self, new_instructions: str):
        """
        Update session instructions dynamically.
        CRITICAL: Must preserve ALL session settings when updating!
        """
        if not self.conversation:
            logger.warning("No active conversation to update")
            return
        
        try:
            # Map format strings to enums (MUST preserve from initial setup!)
            input_format = (
                AudioFormat.PCM_16000HZ_MONO_16BIT if self.input_format == 'pcm16'
                else AudioFormat.PCM_24000HZ_MONO_16BIT
            )
            output_format = (
                AudioFormat.PCM_24000HZ_MONO_16BIT if self.output_format == 'pcm24'
                else AudioFormat.PCM_16000HZ_MONO_16BIT
            )
            
            # CRITICAL: Update session with ALL parameters to prevent format reset
            self.conversation.update_session(
                output_modalities=[MultiModality.TEXT, MultiModality.AUDIO],
                voice=self.voice,
                input_audio_format=input_format,
                output_audio_format=output_format,  # Must preserve format!
                enable_input_audio_transcription=True,
                input_audio_transcription_model=self.transcription_model,
                enable_turn_detection=True,
                turn_detection_type='server_vad',
                prefix_padding_ms=self.vad_prefix_ms,
                turn_detection_threshold=self.vad_threshold,
                turn_detection_silence_duration_ms=self.vad_silence_ms,
                instructions=new_instructions
            )
            
            logger.debug(f"Instructions updated (format preserved): {new_instructions[:50]}...")
        
        except Exception as e:
            logger.error(f"Failed to update instructions: {e}", exc_info=True)
    
    def create_greeting(self, greeting_text: str = "Hello! How can I help you today?"):
        """
        Create an initial greeting response from Omni.
        This triggers Omni to speak the greeting without user input.
        """
        if not self.conversation:
            logger.warning("No active conversation for greeting")
            return
        
        try:
            # Create a response with the greeting text as instructions
            # This will make Omni generate audio for the greeting
            self.conversation.create_response(
                instructions=greeting_text,
                output_modalities=[MultiModality.TEXT, MultiModality.AUDIO]
            )
            logger.info(f"Greeting created: {greeting_text}")
        except Exception as e:
            logger.error(f"Failed to create greeting: {e}", exc_info=True)
    
    def close(self):
        """Close conversation"""
        if self.conversation:
            try:
                self.conversation.close()
                logger.info("Conversation closed")
            except Exception as e:
                logger.error(f"Failed to close conversation: {e}")

