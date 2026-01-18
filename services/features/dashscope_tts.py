"""
Dashscope Real-time TTS Service
==============================

Service for generating speech audio using Dashscope's real-time TTS API.
Uses native WebSocket implementation for fully async streaming.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from pathlib import Path
from typing import Optional, AsyncGenerator
import logging
import os

from clients.tts_realtime_client import (
    TTSRealtimeClient,
    SessionMode,
    AudioFormat,
)
from config.settings import config


logger = logging.getLogger(__name__)

# ============================================================================
# Configuration
# ============================================================================

# Default voice mapping for different roles
VOICE_MAPPING = {
    'qwen': 'Kai',         # Qwen uses Kai voice
    'doubao': 'Cherry',    # Doubao uses Cherry voice
    'deepseek': 'Serena',  # DeepSeek uses Serena voice
    'kimi': 'Mia',         # Kimi uses Mia voice
    'judge': 'Neil',       # 阿闻 - 专业新闻主持人
    'default': 'Cherry',
}

# Model selection - using flash-realtime for best performance
TTS_MODEL = 'qwen3-tts-flash-realtime'

# ============================================================================
# Helper Functions
# ============================================================================


# ============================================================================
# TTS Service
# ============================================================================

class DashscopeTtsService:
    """Service for generating speech using Dashscope real-time TTS"""

    def __init__(self):
        self.api_key: Optional[str] = None
        self._initialize_api_key()

    def _initialize_api_key(self):
        """Initialize Dashscope API key from environment or config"""
        # Try environment variable first
        self.api_key = os.getenv('DASHSCOPE_API_KEY')

        # Fallback to QWEN_API_KEY (same as Dashscope)
        if not self.api_key:
            self.api_key = config.QWEN_API_KEY

        if not self.api_key:
            logger.warning("[TTS] DASHSCOPE_API_KEY not configured - TTS will be disabled")
        else:
            logger.info("[TTS] Dashscope API key initialized")

    def is_available(self) -> bool:
        """Check if TTS service is available"""
        return self.api_key is not None

    def get_voice_for_model(self, model_id: Optional[str]) -> str:
        """Get voice name for a given model ID"""
        if not model_id:
            return VOICE_MAPPING['default']

        # Normalize physical model names to logical names
        # Handle cases like 'ark-kimi' -> 'kimi', 'ark-doubao' -> 'doubao', 'ark-deepseek' -> 'deepseek'
        model_id = model_id.lower()
        if model_id.startswith('ark-'):
            model_id = model_id[4:]  # Remove 'ark-' prefix

        return VOICE_MAPPING.get(model_id, VOICE_MAPPING['default'])

    async def synthesize_text(
        self,
        text: str,
        voice: Optional[str] = None,
        model_id: Optional[str] = None,
        output_format: Optional[AudioFormat] = None,
    ) -> Optional[bytes]:
        """
        Synthesize text to speech and return audio bytes.

        Args:
            text: Text to synthesize
            voice: Voice name (optional, will use model_id mapping if not provided)
            model_id: Model ID to determine voice (e.g., 'qwen', 'deepseek')
            output_format: Audio format (defaults to MP3_24000HZ_MONO)

        Returns:
            Audio bytes (MP3 format) or None if synthesis failed
        """
        if not self.is_available():
            logger.warning("[TTS] Service not available, skipping synthesis")
            return None

        if not text or not text.strip():
            logger.warning("[TTS] Empty text provided")
            return None

        # Determine voice
        if not voice:
            voice = self.get_voice_for_model(model_id)

        # Use default format if not specified
        if output_format is None:
            output_format = AudioFormat.MP3_24000HZ_MONO

        logger.debug("[TTS] Synthesizing text (length=%s, voice=%s)", len(text), voice)

        try:
            # Collect audio chunks
            audio_chunks = []

            def on_audio_chunk(audio_bytes: bytes):
                audio_chunks.append(audio_bytes)

            # Create TTS client
            client = TTSRealtimeClient(
                api_key=self.api_key,
                model=TTS_MODEL,
                voice=voice,
                mode=SessionMode.SERVER_COMMIT,
                response_format=output_format,
                sample_rate=24000,  # Default sample rate
                language_type=None,  # Auto-detect language
                on_audio_chunk=on_audio_chunk,
            )

            # Connect and synthesize
            await client.connect()
            await client.wait_for_session_created()

            # Send text
            await client.append_text(text)

            # Finish session
            await client.finish_session()

            # Wait for completion
            await client.wait_for_response_done(timeout=30.0)

            # Close connection
            await client.close()

            # Combine audio chunks
            if audio_chunks:
                audio_bytes = b''.join(audio_chunks)
                logger.info("[TTS] Successfully synthesized %s bytes", len(audio_bytes))
                return audio_bytes
            else:
                logger.warning("[TTS] Synthesis returned no audio")
                return None

        except Exception as e:
            logger.error("[TTS] Synthesis error: %s", e, exc_info=True)
            return None

    async def synthesize_stream(
        self,
        text_chunks: AsyncGenerator[str, None],
        voice: Optional[str] = None,
        model_id: Optional[str] = None,
        output_format: Optional[AudioFormat] = None,
    ) -> AsyncGenerator[bytes, None]:
        """
        Stream TTS audio as text chunks arrive.

        Args:
            text_chunks: Async generator yielding text chunks
            voice: Voice name (optional)
            model_id: Model ID to determine voice (optional)
            output_format: Audio format (optional)

        Yields:
            Audio chunks (bytes) as they are generated
        """
        if not self.is_available():
            logger.warning("[TTS] Service not available, skipping synthesis")
            return

        # Determine voice
        if not voice:
            voice = self.get_voice_for_model(model_id)

        # Use default format if not specified
        if output_format is None:
            output_format = AudioFormat.MP3_24000HZ_MONO

        try:
            # Create TTS client with streaming
            client = TTSRealtimeClient(
                api_key=self.api_key,
                model=TTS_MODEL,
                voice=voice,
                mode=SessionMode.SERVER_COMMIT,
                response_format=output_format,
                sample_rate=24000,  # Default sample rate
                language_type=None,  # Auto-detect language
            )

            # Use built-in streaming method
            async for audio_chunk in client.synthesize_stream(text_chunks, voice):
                yield audio_chunk

        except Exception as e:
            logger.error("[TTS] Streaming synthesis error: %s", e, exc_info=True)

    async def synthesize_to_file(
        self,
        text: str,
        output_path: Path,
        voice: Optional[str] = None,
        model_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        Synthesize text to speech and save to file.

        Args:
            text: Text to synthesize
            output_path: Path to save audio file
            voice: Voice name (optional)
            model_id: Model ID to determine voice (optional)

        Returns:
            File path if successful, None otherwise
        """
        audio_bytes = await self.synthesize_text(text, voice, model_id)

        if not audio_bytes:
            return None

        try:
            # Ensure directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Write audio file
            with open(output_path, 'wb') as f:
                f.write(audio_bytes)

            logger.info("[TTS] Saved audio to %s", output_path)
            return str(output_path)

        except Exception as e:
            logger.error("[TTS] Failed to save audio file: %s", e, exc_info=True)
            return None


# ============================================================================
# Global Instance
# ============================================================================

_tts_service: Optional[DashscopeTtsService] = None

def get_tts_service() -> DashscopeTtsService:
    """Get global TTS service instance"""
    global _tts_service
    if _tts_service is None:
        _tts_service = DashscopeTtsService()
    return _tts_service
