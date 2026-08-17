"""CosyVoice v3.5 voice design (no system voices).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Optional

import httpx

from clients.llm.http_client_manager import get_httpx_manager
from config.dashscope_urls import (
    build_api_v1_base,
    build_dashscope_headers,
    normalize_dashscope_region,
)
from config.settings import config
from services.kitty.asr.fun_asr_realtime import resolve_dashscope_api_key
from services.utils.error_types import FILE_IO_ERRORS, LLM_PIPELINE_ERRORS

logger = logging.getLogger(__name__)

# Prefix: digits + lowercase, max 10 chars (DashScope enrollment rule).
DESIGNED_VOICE_PREFIX = "mgv35f"
DESIGNED_VOICE_PROMPT = "年轻女性教师，音色清亮柔和，语速适中，吐字清晰，情绪平稳亲切，适合课堂讲解与旁白。"
DESIGNED_VOICE_PREVIEW = "同学们好，欢迎来到思维讲堂。今天我们一起把这张图讲清楚。"
_VOICE_DESIGN_ERRORS = LLM_PIPELINE_ERRORS + (httpx.HTTPError,)


class _DesignedVoiceHolder:
    """Process-local designed voice id (avoids module global mutation)."""

    voice_id: str = ""
    lock: Optional[asyncio.Lock] = None
    loop_id: Optional[int] = None


_DESIGNED_VOICE = _DesignedVoiceHolder()


def cached_designed_voice_id() -> str:
    """Process-local designed voice id, or empty before the first ensure()."""
    return _DESIGNED_VOICE.voice_id


def reset_designed_voice_for_tests() -> None:
    """Clear the cached designed voice (pytest)."""
    _DESIGNED_VOICE.voice_id = ""
    _DESIGNED_VOICE.lock = None
    _DESIGNED_VOICE.loop_id = None


def _designed_voice_lock() -> asyncio.Lock:
    loop = asyncio.get_running_loop()
    loop_id = id(loop)
    if _DESIGNED_VOICE.lock is None or _DESIGNED_VOICE.loop_id != loop_id:
        _DESIGNED_VOICE.lock = asyncio.Lock()
        _DESIGNED_VOICE.loop_id = loop_id
    return _DESIGNED_VOICE.lock


def build_list_voice_payload(prefix: str) -> dict[str, Any]:
    """``list_voice`` body for CosyVoice enrollment."""
    return {
        "model": "voice-enrollment",
        "input": {
            "action": "list_voice",
            "prefix": prefix,
            "page_index": 0,
            "page_size": 10,
        },
    }


def build_create_voice_payload(
    target_model: str,
    *,
    prefix: str,
    voice_prompt: str,
    preview_text: str,
) -> dict[str, Any]:
    """``create_voice`` body for CosyVoice voice design (no sample audio)."""
    return {
        "model": "voice-enrollment",
        "input": {
            "action": "create_voice",
            "target_model": target_model,
            "prefix": prefix,
            "voice_prompt": voice_prompt,
            "preview_text": preview_text,
        },
        "parameters": {
            "sample_rate": 24000,
            "response_format": "wav",
        },
    }


def parse_ok_voice_ids(payload: dict[str, Any]) -> list[str]:
    """Return callable voice ids from a ``list_voice`` response."""
    output = payload.get("output")
    if not isinstance(output, dict):
        return []
    raw_list = output.get("voice_list")
    if not isinstance(raw_list, list):
        return []
    found: list[str] = []
    for item in raw_list:
        if not isinstance(item, dict):
            continue
        voice_id = str(item.get("voice_id") or "").strip()
        status = str(item.get("status") or "").strip().upper()
        if voice_id and status in ("OK", "CALLABLE", ""):
            found.append(voice_id)
    return found


def build_query_voice_payload(voice_id: str) -> dict[str, Any]:
    """``query_voice`` body for one designed / cloned id."""
    return {
        "model": "voice-enrollment",
        "input": {
            "action": "query_voice",
            "voice_id": voice_id,
        },
    }


def parse_query_voice_ok(payload: dict[str, Any], expected_id: str) -> bool:
    """True when ``query_voice`` returns a callable id."""
    output = payload.get("output")
    if not isinstance(output, dict):
        return False
    voice_id = str(output.get("voice_id") or output.get("voice") or "").strip()
    status = str(output.get("status") or "").strip().upper()
    if voice_id != expected_id:
        return False
    return status in ("OK", "CALLABLE", "")


def parse_created_voice_id(payload: dict[str, Any]) -> str:
    """Return the new voice id from a ``create_voice`` response."""
    output = payload.get("output")
    if not isinstance(output, dict):
        message = str(payload.get("message") or payload.get("code") or "Voice design failed")
        raise RuntimeError(message)
    voice_id = str(output.get("voice_id") or output.get("voice") or "").strip()
    if not voice_id:
        raise RuntimeError("Voice design create returned no voice id")
    return voice_id


def _enrollment_api_base() -> str:
    workspace_id = config.DASHSCOPE_WORKSPACE_ID
    region = normalize_dashscope_region(str(getattr(config, "DASHSCOPE_REGION", None) or "cn-beijing"))
    return build_api_v1_base(workspace_id=workspace_id, region=region)


async def _post_enrollment(body: dict[str, Any]) -> dict[str, Any]:
    api_key = resolve_dashscope_api_key()
    if not api_key:
        raise RuntimeError("DashScope API key not configured for CosyVoice voice design")
    workspace_id = config.DASHSCOPE_WORKSPACE_ID
    headers = build_dashscope_headers(api_key, workspace_id=workspace_id)
    client = await get_httpx_manager().get_client(
        "cosyvoice-enrollment",
        _enrollment_api_base(),
        timeout=60.0,
        stream_timeout=60.0,
    )
    response = await client.post("services/audio/tts/customization", headers=headers, json=body)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise RuntimeError("Voice enrollment returned a non-object payload")
    return data


async def ensure_cosyvoice_designed_voice(target_model: str) -> str:
    """Reuse or create a v3.5 designed voice for ``target_model``."""
    cached = _DESIGNED_VOICE.voice_id
    if cached:
        return cached
    async with _designed_voice_lock():
        cached = _DESIGNED_VOICE.voice_id
        if cached:
            return cached
        try:
            listed = await _post_enrollment(build_list_voice_payload(DESIGNED_VOICE_PREFIX))
            existing = parse_ok_voice_ids(listed)
            if existing:
                _DESIGNED_VOICE.voice_id = existing[0]
                logger.info(
                    "Reusing CosyVoice designed voice %s for %s",
                    _DESIGNED_VOICE.voice_id,
                    target_model,
                )
                return _DESIGNED_VOICE.voice_id
            created = await _post_enrollment(
                build_create_voice_payload(
                    target_model,
                    prefix=DESIGNED_VOICE_PREFIX,
                    voice_prompt=DESIGNED_VOICE_PROMPT,
                    preview_text=DESIGNED_VOICE_PREVIEW,
                )
            )
            voice_id = parse_created_voice_id(created)
        except _VOICE_DESIGN_ERRORS as exc:
            raise RuntimeError(f"CosyVoice voice design failed: {exc}") from exc
        _DESIGNED_VOICE.voice_id = voice_id
        logger.info("Created CosyVoice designed voice %s for %s", voice_id, target_model)
        return voice_id


def _project_env_path() -> Path:
    return Path(__file__).resolve().parents[3] / ".env"


def _upsert_env_keys(env_path: Path, updates: dict[str, str]) -> bool:
    raw = env_path.read_text(encoding="utf-8")
    newline = "\r\n" if "\r\n" in raw else "\n"
    lines = raw.splitlines()
    seen: set[str] = set()
    rewritten: list[str] = []
    for line in lines:
        stripped = line.strip()
        key = ""
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
        if key in updates:
            rewritten.append(f"{key}={updates[key]}")
            seen.add(key)
        else:
            rewritten.append(line)
    for key, value in updates.items():
        if key not in seen:
            rewritten.append(f"{key}={value}")
    new_raw = newline.join(rewritten)
    if raw.endswith(("\n", "\r\n")):
        new_raw += newline
    if new_raw == raw:
        return False
    env_path.write_text(new_raw, encoding="utf-8")
    return True


def persist_kitty_tts_pin(
    model: str,
    voice: str,
    *,
    env_path: Optional[Path] = None,
) -> bool:
    """Pin model + voice in process env and ``.env`` (skipped under pytest)."""
    pinned_model = (model or "").strip()
    pinned_voice = (voice or "").strip()
    if not pinned_model or not pinned_voice:
        return False
    under_pytest = bool(os.getenv("PYTEST_CURRENT_TEST"))
    if not under_pytest or env_path is not None:
        os.environ["KITTY_TTS_MODEL"] = pinned_model
        os.environ["KITTY_TTS_VOICE"] = pinned_voice
    if env_path is None and under_pytest:
        return False
    target = env_path or _project_env_path()
    if not target.is_file():
        return False
    try:
        wrote = _upsert_env_keys(
            target,
            {
                "KITTY_TTS_MODEL": pinned_model,
                "KITTY_TTS_VOICE": pinned_voice,
            },
        )
    except FILE_IO_ERRORS as exc:
        logger.warning("Could not persist KITTY_TTS_* to %s: %s", target, exc)
        return False
    if wrote:
        logger.info("Pinned CosyVoice %s / %s in %s", pinned_model, pinned_voice, target)
    return wrote


async def locate_cosyvoice_v35_voice(preferred: str, target_model: str) -> str:
    """Return a callable v3.5 voice id, or empty if none can be located."""
    wanted = (preferred or "").strip()
    cached = _DESIGNED_VOICE.voice_id
    if cached and (not wanted or wanted == cached):
        return cached
    if wanted:
        try:
            queried = await _post_enrollment(build_query_voice_payload(wanted))
            if parse_query_voice_ok(queried, wanted):
                _DESIGNED_VOICE.voice_id = wanted
                persist_kitty_tts_pin(target_model, wanted)
                return wanted
            logger.warning("KITTY_TTS_VOICE %s is not callable on this workspace", wanted)
        except _VOICE_DESIGN_ERRORS as exc:
            logger.warning("query_voice failed for %s: %s", wanted, exc)
    try:
        voice_id = await ensure_cosyvoice_designed_voice(target_model)
    except _VOICE_DESIGN_ERRORS as exc:
        logger.warning("CosyVoice v3.5 voice locate failed: %s", exc)
        return ""
    if voice_id:
        persist_kitty_tts_pin(target_model, voice_id)
    return voice_id
