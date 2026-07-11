"""DashScope recording-file (batch) speech-to-text for audio sources.

Transcribes uploaded audio files via DashScope's asynchronous recording-file
recognition API (submit task → poll → download result JSON). Used by the
document processor to turn audio sources (mp3/wav/m4a/...) into text that is then
chunked and indexed like any other File Center source.

The async API only accepts a **publicly reachable** audio URL (no direct upload),
so callers must provide a URL DashScope can fetch (see ``audio_hosting``). The
model is configurable via ``DASHSCOPE_ASR_FILETRANS_MODEL`` (default ``fun-asr-flash-2026-06-15``).

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Tuple, Type

import httpx

from config.settings import config
from services.knowledge.audio_hosting import publish_audio, revoke_audio

logger = logging.getLogger(__name__)

# Audio MIME types accepted as File Center sources (extension → mime).
AUDIO_EXTENSIONS: Dict[str, str] = {
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".m4a": "audio/mp4",
    ".aac": "audio/aac",
    ".flac": "audio/flac",
    ".ogg": "audio/ogg",
    ".opus": "audio/opus",
    ".amr": "audio/amr",
    ".wma": "audio/x-ms-wma",
}
AUDIO_MIME_TYPES = frozenset(AUDIO_EXTENSIONS.values())

# Submit/poll endpoints are relative to DASHSCOPE_API_URL (".../api/v1/").
_SUBMIT_PATH = "services/audio/asr/transcription"
_TASK_PATH = "tasks/{task_id}"

# Polling: filetrans can take a while for long audio; bound total wait.
_POLL_INTERVAL_SEC = 5.0
_MAX_POLL_SEC = 1800.0  # 30 minutes
_TERMINAL_OK = "SUCCEEDED"
_TERMINAL_STATES = frozenset({"SUCCEEDED", "FAILED", "CANCELED"})

# httpx transport/status errors + JSON/shape errors for narrow excepts.
_ASR_ERRORS: Tuple[Type[Exception], ...] = (
    httpx.HTTPError,
    ConnectionError,
    TimeoutError,
    OSError,
    ValueError,
    TypeError,
    KeyError,
    IndexError,
)


def is_audio_mime(file_type: Optional[str]) -> bool:
    """True when a MIME type is a supported audio source type."""
    return bool(file_type) and file_type in AUDIO_MIME_TYPES


def _resolve_api_key() -> str:
    """Prefer DASHSCOPE_API_KEY, then QWEN_API_KEY (DashScope ASR docs)."""
    for candidate in (config.DASHSCOPE_API_KEY, config.QWEN_API_KEY):
        if candidate and str(candidate).strip():
            return str(candidate).strip()
    raise ValueError("DashScope API key required for audio transcription")


def _base_url() -> str:
    return config.DASHSCOPE_API_URL


def _submit_task(client: httpx.Client, file_url: str, language_hints: Optional[List[str]]) -> str:
    """Submit an async transcription task; return the DashScope task id."""
    parameters: Dict[str, Any] = {"channel_id": [0]}
    if language_hints:
        parameters["language_hints"] = language_hints

    payload = {
        "model": config.DASHSCOPE_ASR_FILETRANS_MODEL,
        "input": {"file_urls": [file_url]},
        "parameters": parameters,
    }
    headers = {
        "Authorization": f"Bearer {_resolve_api_key()}",
        "Content-Type": "application/json",
        "X-DashScope-Async": "enable",
    }
    response = client.post(f"{_base_url()}{_SUBMIT_PATH}", headers=headers, json=payload)
    response.raise_for_status()
    output = response.json().get("output", {})
    task_id = output.get("task_id")
    if not task_id:
        raise ValueError(f"DashScope ASR submit returned no task_id: {output}")
    logger.info("[AudioASR] Submitted transcription task %s (model=%s)", task_id, payload["model"])
    return str(task_id)


def _poll_task(client: httpx.Client, task_id: str) -> Dict[str, Any]:
    """Poll a transcription task until it reaches a terminal state; return output."""
    headers = {"Authorization": f"Bearer {_resolve_api_key()}"}
    url = f"{_base_url()}{_TASK_PATH.format(task_id=task_id)}"
    deadline = time.time() + _MAX_POLL_SEC
    while True:
        response = client.get(url, headers=headers)
        response.raise_for_status()
        output = response.json().get("output", {})
        status = (output.get("task_status") or "").upper()
        if status in _TERMINAL_STATES:
            if status != _TERMINAL_OK:
                raise ValueError(f"DashScope ASR task {task_id} ended with status {status}")
            return output
        if time.time() > deadline:
            raise TimeoutError(f"DashScope ASR task {task_id} timed out after {_MAX_POLL_SEC:.0f}s")
        time.sleep(_POLL_INTERVAL_SEC)


def _collect_transcription_urls(output: Dict[str, Any]) -> List[str]:
    """Pull per-file transcription result URLs from a finished task output."""
    urls: List[str] = []
    for item in output.get("results", []) or []:
        if isinstance(item, dict) and item.get("subtask_status", "SUCCEEDED").upper() == "SUCCEEDED":
            url = item.get("transcription_url")
            if url:
                urls.append(str(url))
    # qwen3-asr-flash-filetrans nests a single result under "result".
    single = output.get("result")
    if isinstance(single, dict) and single.get("transcription_url"):
        urls.append(str(single["transcription_url"]))
    return urls


def _download_transcript_text(client: httpx.Client, transcription_url: str) -> str:
    """Download a result JSON and concatenate its paragraph-level transcripts."""
    response = client.get(transcription_url)
    response.raise_for_status()
    data = response.json()
    transcripts = data.get("transcripts", []) if isinstance(data, dict) else []
    parts = [str(t.get("text", "")).strip() for t in transcripts if isinstance(t, dict) and t.get("text")]
    return "\n".join(part for part in parts if part)


def transcribe_audio_url(file_url: str, language_hints: Optional[List[str]] = None) -> str:
    """Transcribe a publicly reachable audio URL to text (synchronous submit/poll).

    Raises ``ValueError``/``TimeoutError`` (or wrapped transport errors) on
    failure so the caller can mark the source as failed.
    """
    if not file_url:
        raise ValueError("Audio file URL is required for transcription")

    try:
        with httpx.Client(timeout=60.0) as client:
            task_id = _submit_task(client, file_url, language_hints)
            output = _poll_task(client, task_id)
            urls = _collect_transcription_urls(output)
            if not urls:
                raise ValueError(f"DashScope ASR task {task_id} produced no transcription URL")
            text = "\n".join(_download_transcript_text(client, url) for url in urls).strip()
    except _ASR_ERRORS as exc:
        logger.error("[AudioASR] Transcription failed for %s: %s", file_url, exc)
        raise ValueError(f"Audio transcription failed: {exc}") from exc

    if not text:
        raise ValueError("Audio transcription returned empty text")
    logger.info("[AudioASR] Transcribed %d characters from audio", len(text))
    return text


def transcribe_audio_file(file_path: str, language_hints: Optional[List[str]] = None) -> str:
    """Transcribe a local audio file by hosting it temporarily, then calling ASR.

    Publishes the file behind a short-lived public token so DashScope can fetch
    it, transcribes, then revokes the token. Raises ``ValueError`` on failure.
    """
    try:
        token, file_url = publish_audio(file_path)
    except (RuntimeError, ValueError) as exc:
        raise ValueError(f"Audio hosting unavailable for transcription: {exc}") from exc

    try:
        return transcribe_audio_url(file_url, language_hints=language_hints or ["zh", "en"])
    finally:
        revoke_audio(token)
