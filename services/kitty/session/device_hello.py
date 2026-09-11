"""Hello handshake: listen_mode, device registry, user Kitty defaults.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional

from services.kitty.asr.audio_format import ASR_AUDIO_FORMATS
from services.kitty.infra.redis.kitty_redis_keys import (
    kitty_device_index_key,
    kitty_device_user_key,
    kitty_user_defaults_key,
)
from services.kitty.session.listen_modes import (
    LISTEN_MANUAL,
    ListenMode,
    normalize_listen_mode,
    parse_hello_listen_mode,
    set_session_listen_mode,
)
from services.kitty.session.runtime_state import voice_sessions
from services.kitty.session.voice_phase import session_voice_phase
from services.redis.redis_async_client import get_async_redis
from services.utils.error_types import REDIS_ERRORS

logger = logging.getLogger(__name__)

DEVICE_TTL_SECONDS = 7 * 24 * 3600
DEFAULTS_TTL_SECONDS = 30 * 24 * 3600
_MAX_DEVICE_ID_LEN = 80
_MAX_FIRMWARE_LEN = 40


def _clip(raw: object, limit: int) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    return text[:limit]


def parse_device_id(message: dict) -> str:
    """Stable client id from hello (watch MAC / web uuid)."""
    return _clip(message.get("device_id"), _MAX_DEVICE_ID_LEN)


def parse_firmware(message: dict) -> str:
    """Firmware or web build label from hello."""
    return _clip(message.get("firmware"), _MAX_FIRMWARE_LEN)


async def load_user_kitty_defaults(user_id: int) -> Dict[str, Any]:
    """Per-user listen_mode / TTS defaults. Missing keys use PTT + TTS on."""
    fallback = {"listen_mode": LISTEN_MANUAL, "tts_enabled": True}
    try:
        redis = get_async_redis()
        raw = await redis.get(kitty_user_defaults_key(user_id))
    except REDIS_ERRORS as exc:
        logger.warning("Kitty defaults read failed user=%s: %s", user_id, exc)
        return fallback
    if not isinstance(raw, (str, bytes)) or not raw:
        return fallback
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return fallback
    if not isinstance(payload, dict):
        return fallback
    tts_raw = payload.get("tts_enabled")
    return {
        "listen_mode": normalize_listen_mode(payload.get("listen_mode")),
        "tts_enabled": bool(tts_raw) if tts_raw is not None else True,
    }


async def save_user_kitty_defaults(
    user_id: int,
    *,
    listen_mode: object = None,
    tts_enabled: object = None,
) -> Dict[str, Any]:
    """Merge and persist user Kitty defaults."""
    current = await load_user_kitty_defaults(user_id)
    if listen_mode is not None:
        current["listen_mode"] = normalize_listen_mode(listen_mode)
    if tts_enabled is not None:
        current["tts_enabled"] = bool(tts_enabled)
    try:
        redis = get_async_redis()
        await redis.set(
            kitty_user_defaults_key(user_id),
            json.dumps(current),
            ex=DEFAULTS_TTL_SECONDS,
        )
    except REDIS_ERRORS as exc:
        logger.warning("Kitty defaults write failed user=%s: %s", user_id, exc)
    return current


async def register_hello_device(
    user_id: int,
    *,
    device_id: str,
    firmware: str,
    listen_mode: ListenMode,
    lane: str,
    voice_session_id: str,
) -> None:
    """Remember a client that completed hello (admin device list)."""
    if not device_id:
        return
    record = {
        "device_id": device_id,
        "firmware": firmware,
        "listen_mode": listen_mode,
        "lane": lane,
        "voice_session_id": voice_session_id,
        "user_id": user_id,
        "last_seen": int(time.time()),
    }
    try:
        redis = get_async_redis()
        pipe = redis.pipeline()
        pipe.hset(kitty_device_user_key(user_id), device_id, json.dumps(record))
        pipe.expire(kitty_device_user_key(user_id), DEVICE_TTL_SECONDS)
        pipe.sadd(kitty_device_index_key(), str(user_id))
        await pipe.execute()
    except REDIS_ERRORS as exc:
        logger.warning("Kitty device hello persist failed user=%s: %s", user_id, exc)


async def list_hello_devices(*, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Admin: devices that completed hello. Optional filter by user."""
    try:
        redis = get_async_redis()
        if user_id is not None:
            user_ids = [int(user_id)]
        else:
            raw_ids = await redis.smembers(kitty_device_index_key())
            user_ids = []
            for item in raw_ids or []:
                try:
                    user_ids.append(int(item))
                except (TypeError, ValueError):
                    continue
        devices: List[Dict[str, Any]] = []
        for uid in user_ids:
            rows = await redis.hgetall(kitty_device_user_key(uid))
            if not rows:
                continue
            for raw in rows.values():
                parsed = _parse_device_record(raw, uid)
                if parsed is not None:
                    devices.append(parsed)
        devices.sort(key=lambda row: int(row.get("last_seen") or 0), reverse=True)
        return devices
    except REDIS_ERRORS as exc:
        logger.warning("Kitty device list failed: %s", exc)
        return []


def _parse_device_record(raw: object, user_id: int) -> Optional[Dict[str, Any]]:
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="replace")
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    device_id = _clip(payload.get("device_id"), _MAX_DEVICE_ID_LEN)
    if not device_id:
        return None
    return {
        "device_id": device_id,
        "firmware": _clip(payload.get("firmware"), _MAX_FIRMWARE_LEN),
        "listen_mode": normalize_listen_mode(payload.get("listen_mode")),
        "lane": _clip(payload.get("lane"), 20) or "unknown",
        "voice_session_id": _clip(payload.get("voice_session_id"), 40),
        "user_id": user_id,
        "last_seen": int(payload.get("last_seen") or 0),
    }


def list_live_voice_sessions() -> List[Dict[str, Any]]:
    """In-process session strip for the admin tab (no secrets)."""
    rows: List[Dict[str, Any]] = []
    for sid, sess in voice_sessions.items():
        if not isinstance(sess, dict):
            continue
        raw_user = sess.get("user_id")
        try:
            user_id = int(raw_user) if raw_user is not None else None
        except (TypeError, ValueError):
            user_id = None
        lane_raw = sess.get("_kitty_client_lane")
        lane = lane_raw.strip() if isinstance(lane_raw, str) and lane_raw.strip() else "—"
        scope_raw = sess.get("diagram_session_id")
        scope = scope_raw.strip() if isinstance(scope_raw, str) else ""
        rows.append(
            {
                "voice_session_id": sid,
                "user_id": user_id,
                "scope": scope,
                "lane": lane,
                "listen_mode": sess.get("_kitty_listen_mode") or LISTEN_MANUAL,
                "voice_phase": session_voice_phase(sid),
            }
        )
    return rows


async def apply_hello_to_session(
    voice_session_id: str,
    user_id: int,
    message: dict,
) -> Dict[str, Any]:
    """Resolve listen_mode, register the device, return the hello ack payload."""
    defaults = await load_user_kitty_defaults(user_id)
    client_mode = parse_hello_listen_mode(message)
    mode = client_mode if client_mode is not None else normalize_listen_mode(defaults.get("listen_mode"))
    set_session_listen_mode(voice_session_id, mode)
    device_id = parse_device_id(message)
    firmware = parse_firmware(message)
    sess = voice_sessions.get(voice_session_id)
    lane_raw = sess.get("_kitty_client_lane") if isinstance(sess, dict) else None
    lane = lane_raw.strip() if isinstance(lane_raw, str) and lane_raw.strip() else "unknown"
    if device_id and isinstance(sess, dict):
        sess["_kitty_device_id"] = device_id
        sess["_kitty_firmware"] = firmware
        await register_hello_device(
            user_id,
            device_id=device_id,
            firmware=firmware,
            listen_mode=mode,
            lane=lane,
            voice_session_id=voice_session_id,
        )
    return {
        "type": "hello",
        "session_id": voice_session_id,
        "listen_mode": mode,
        "asr_commit_mode": "final_or_stopped" if mode == "auto" else "release_only",
        "asr_audio_formats": list(ASR_AUDIO_FORMATS),
    }
