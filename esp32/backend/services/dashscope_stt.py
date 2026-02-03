"""
DashScope Real-time Speech Recognition Service
Integrates DashScope STT API for server-side speech-to-text processing
"""

import asyncio
import base64
import json
import logging
from typing import Callable, Optional

try:
    from dashscope import Recognition
    from dashscope.audio.asr.recognition import RecognitionParam, RecognitionResult
    from dashscope.common import ResultCallback
except ImportError:
    Recognition = None
    RecognitionParam = None
    RecognitionResult = None
    ResultCallback = None
from dashscope.audio.asr.recognition import RecognitionParam, RecognitionResult
from dashscope.common import ResultCallback

try:
    from config.settings import config
except ImportError:
    config = type('Config', (), {'get': lambda self, key, default=None: default})()

logger = logging.getLogger(__name__)


class DashScopeSTTService:
    """DashScope Real-time Speech Recognition Service"""

    def __init__(self, api_key: Optional[str] = None, model: str = "fun-asr-realtime"):
        self.api_key = api_key or config.get("DASHSCOPE_API_KEY")
        self.model = model
        self.sessions = {}

    def is_available(self) -> bool:
        """Check if STT service is available"""
        return bool(self.api_key)

    async def create_recognition_session(
        self,
        session_id: str,
        on_transcription: Callable[[str, bool], None],
        on_error: Optional[Callable[[Exception], None]] = None,
    ) -> Recognition:
        """Create a real-time STT session"""
        if not self.is_available():
            raise ValueError("DashScope API key not configured")

        param = RecognitionParam.builder()\
            .model(self.model)\
            .apiKey(self.api_key)\
            .format("pcm")\
            .sampleRate(16000)\
            .build()

        recognizer = Recognition()

        callback = ResultCallback[RecognitionResult]()
        callback.on_event = lambda result: self._handle_transcription(
            session_id, result, on_transcription
        )
        callback.on_error = on_error or (lambda e: logger.error("STT error: %s", e))
        callback.on_complete = lambda: logger.info("STT session %s completed", session_id)

        recognizer.call(param, callback)
        self.sessions[session_id] = recognizer

        logger.info("Created STT session %s with model %s", session_id, self.model)
        return recognizer

    def _handle_transcription(
        self,
        session_id: str,
        result: RecognitionResult,
        callback: Callable[[str, bool], None],
    ):
        """Handle transcription result"""
        if result.isSentenceEnd():
            text = result.getSentence().getText()
            logger.debug("STT final: %s", text)
            callback(text, True)
        else:
            text = result.getSentence().getText()
            logger.debug("STT intermediate: %s", text)
            callback(text, False)

    async def send_audio_frame(self, session_id: str, audio_data: bytes):
        """Send audio frame to STT service"""
        if session_id not in self.sessions:
            raise ValueError(f"STT session {session_id} not found")

        recognizer = self.sessions[session_id]
        recognizer.sendAudioFrame(audio_data)

    async def close_session(self, session_id: str):
        """Close STT session"""
        if session_id in self.sessions:
            recognizer = self.sessions[session_id]
            recognizer.getDuplexApi().close(1000, "Session ended")
            del self.sessions[session_id]
            logger.info("Closed STT session %s", session_id)


_stt_service: Optional[DashScopeSTTService] = None


def get_stt_service() -> DashScopeSTTService:
    """Get singleton STT service instance"""
    global _stt_service
    if _stt_service is None:
        _stt_service = DashScopeSTTService()
    return _stt_service