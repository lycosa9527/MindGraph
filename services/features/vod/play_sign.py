"""Tencent VOD player signature (psign) as official JWT HS256.

Spec: https://cloud.tencent.com/document/product/266/45554
Key is the default-distribution PlayKey (播放密钥).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from typing import Any, Mapping, Optional

JWT_HEADER = {"alg": "HS256", "typ": "JWT"}
DEFAULT_AUDIO_VIDEO_TYPE = "RawAdaptive"
DEFAULT_ADAPTIVE_DEFINITION = 10


def _b64url(data: bytes) -> str:
    """JWT base64url without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def compact_json_bytes(payload: Mapping[str, Any]) -> bytes:
    """Stable compact JSON for HMAC input."""
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def default_content_info(adaptive_definition: int = DEFAULT_ADAPTIVE_DEFINITION) -> dict[str, Any]:
    """Official required contentInfo for adaptive HLS after transcode."""
    return {
        "audioVideoType": DEFAULT_AUDIO_VIDEO_TYPE,
        "rawAdaptiveDefinition": int(adaptive_definition),
    }


def build_psign_payload(
    app_id: int,
    file_id: str,
    current_time: int,
    expire_time: int,
    content_info: Optional[Mapping[str, Any]] = None,
    adaptive_definition: int = DEFAULT_ADAPTIVE_DEFINITION,
) -> dict[str, Any]:
    """Build the official psign payload (required fields only)."""
    info = dict(content_info) if content_info is not None else default_content_info(adaptive_definition)
    return {
        "appId": int(app_id),
        "fileId": str(file_id),
        "contentInfo": info,
        "currentTimeStamp": int(current_time),
        "expireTimeStamp": int(expire_time),
    }


def sign_psign(payload: Mapping[str, Any], play_key: str) -> str:
    """HMAC-SHA256 JWT: header.payload.signature with PlayKey."""
    header_b64 = _b64url(compact_json_bytes(JWT_HEADER))
    payload_b64 = _b64url(compact_json_bytes(payload))
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    digest = hmac.new(play_key.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{header_b64}.{payload_b64}.{_b64url(digest)}"


def build_player_psign(
    app_id: int,
    file_id: str,
    play_key: str,
    current_time: int,
    expire_time: int,
    content_info: Optional[Mapping[str, Any]] = None,
    adaptive_definition: int = DEFAULT_ADAPTIVE_DEFINITION,
) -> str:
    """Issue a psign for TCPlayer FileID playback."""
    payload = build_psign_payload(
        app_id=app_id,
        file_id=file_id,
        current_time=current_time,
        expire_time=expire_time,
        content_info=content_info,
        adaptive_definition=adaptive_definition,
    )
    return sign_psign(payload, play_key)
