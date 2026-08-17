"""HTTP clients for CosyVoice / Qwen-Audio SpeechSynthesizer and Qwen-TTS.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

import httpx

from clients.llm.http_client_manager import get_httpx_manager
from config.dashscope_urls import (
    DashScopeRegion,
    build_dashscope_headers,
    build_multimodal_generation_url,
    build_speech_synthesizer_url,
    normalize_dashscope_region,
)
from config.settings import config
from services.kitty.asr.fun_asr_realtime import resolve_dashscope_api_key
from services.tts.http_payloads import (
    decode_audio_b64,
    extract_audio_b64,
    extract_audio_url,
    parse_sse_json_line,
    speech_synthesizer_headers,
)
from services.utils.error_types import LLM_PIPELINE_ERRORS

logger = logging.getLogger(__name__)
_HTTP_ERRORS = LLM_PIPELINE_ERRORS + (httpx.HTTPError,)


def _tts_region() -> DashScopeRegion:
    return normalize_dashscope_region(str(getattr(config, "DASHSCOPE_REGION", None) or "cn-beijing"))


def _auth_headers(*, stream: bool) -> dict[str, str]:
    api_key = resolve_dashscope_api_key()
    if not api_key:
        raise RuntimeError("DashScope API key not configured for TTS HTTP")
    extra = speech_synthesizer_headers(stream=stream)
    return build_dashscope_headers(
        api_key,
        workspace_id=config.DASHSCOPE_WORKSPACE_ID,
        extra=extra or None,
    )


async def _download_audio_url(url: str) -> bytes:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise RuntimeError("TTS audio URL is missing or invalid")
    base = f"{parsed.scheme}://{parsed.netloc}"
    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"
    client = await get_httpx_manager().get_client("tts-result-oss", base, timeout=60.0)
    response = await client.get(path)
    response.raise_for_status()
    return bytes(response.content)


async def _audio_from_payload(payload: dict[str, Any]) -> bytes:
    chunk = decode_audio_b64(extract_audio_b64(payload))
    if chunk:
        return chunk
    url = extract_audio_url(payload)
    if url:
        return await _download_audio_url(url)
    return b""


async def _post_json(url: str, body: dict[str, Any], *, stream: bool) -> dict[str, Any]:
    headers = _auth_headers(stream=stream)
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    path = parsed.path or "/"
    client = await get_httpx_manager().get_client("dashscope-tts-http", base, timeout=90.0)
    response = await client.post(path, headers=headers, json=body)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise RuntimeError("TTS HTTP returned a non-object payload")
    return data


async def _post_sse_audio(url: str, body: dict[str, Any]) -> bytes:
    headers = _auth_headers(stream=True)
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    path = parsed.path or "/"
    client = await get_httpx_manager().get_client(
        "dashscope-tts-http-sse",
        base,
        timeout=90.0,
        stream_timeout=120.0,
    )
    chunks: list[bytes] = []
    final_url = ""
    async with client.stream("POST", path, headers=headers, json=body) as response:
        response.raise_for_status()
        async for line in response.aiter_lines():
            payload = parse_sse_json_line(line)
            if payload is None:
                continue
            piece = decode_audio_b64(extract_audio_b64(payload))
            if piece:
                chunks.append(piece)
            url_field = extract_audio_url(payload)
            if url_field:
                final_url = url_field
    if chunks:
        return b"".join(chunks)
    if final_url:
        return await _download_audio_url(final_url)
    return b""


async def synthesize_speech_http(body: dict[str, Any], *, stream: bool = False) -> bytes:
    """CosyVoice / Qwen-Audio-TTS non-realtime synthesizer."""
    url = build_speech_synthesizer_url(
        workspace_id=config.DASHSCOPE_WORKSPACE_ID,
        region=_tts_region(),
    )
    try:
        if stream:
            return await _post_sse_audio(url, body)
        payload = await _post_json(url, body, stream=False)
        return await _audio_from_payload(payload)
    except _HTTP_ERRORS as exc:
        logger.warning("SpeechSynthesizer failed: %s", exc)
        raise RuntimeError(f"SpeechSynthesizer failed: {exc}") from exc


async def synthesize_qwen_tts_http(body: dict[str, Any], *, stream: bool = False) -> bytes:
    """Qwen-TTS non-realtime multimodal-generation synthesizer."""
    url = build_multimodal_generation_url(
        workspace_id=config.DASHSCOPE_WORKSPACE_ID,
        region=_tts_region(),
    )
    try:
        if stream:
            return await _post_sse_audio(url, body)
        payload = await _post_json(url, body, stream=False)
        return await _audio_from_payload(payload)
    except _HTTP_ERRORS as exc:
        logger.warning("Qwen-TTS HTTP failed: %s", exc)
        raise RuntimeError(f"Qwen-TTS HTTP failed: {exc}") from exc


async def synthesize_http_audio(
    protocol: str,
    body: dict[str, Any],
    *,
    stream: bool = False,
) -> bytes:
    """Dispatch one HTTP family. ``protocol`` is ``speech_http`` or ``qwen_http``."""
    if protocol == "qwen_http":
        return await synthesize_qwen_tts_http(body, stream=stream)
    return await synthesize_speech_http(body, stream=stream)
