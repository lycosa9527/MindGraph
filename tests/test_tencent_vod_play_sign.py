"""Pinned-vector tests for Tencent VOD player JWT (psign)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json

from services.features.vod.play_sign import (
    JWT_HEADER,
    build_player_psign,
    build_psign_payload,
    compact_json_bytes,
    default_content_info,
    sign_psign,
)

# Official 45554 example identifiers (PlayKey is 播放密钥, not KEY 防盗链).
OFFICIAL_APP_ID = 1255566655
OFFICIAL_FILE_ID = "4564972818519602447"
OFFICIAL_PLAY_KEY = "TxtyhLlgo7J3iOADIron"
PINNED_CURRENT = 1663064276
PINNED_EXPIRE = 1663294210


def _b64url_decode(segment: str) -> bytes:
    padding = "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode(segment + padding)


def test_default_content_info_is_raw_adaptive() -> None:
    """Official default contentInfo is RawAdaptive HLS template 10."""
    assert default_content_info(10) == {
        "audioVideoType": "RawAdaptive",
        "rawAdaptiveDefinition": 10,
    }


def test_psign_payload_uses_official_required_fields() -> None:
    """JWT payload includes appId, fileId, contentInfo, and both timestamps."""
    payload = build_psign_payload(
        OFFICIAL_APP_ID,
        OFFICIAL_FILE_ID,
        PINNED_CURRENT,
        PINNED_EXPIRE,
        adaptive_definition=10,
    )
    assert payload == {
        "appId": OFFICIAL_APP_ID,
        "fileId": OFFICIAL_FILE_ID,
        "contentInfo": {
            "audioVideoType": "RawAdaptive",
            "rawAdaptiveDefinition": 10,
        },
        "currentTimeStamp": PINNED_CURRENT,
        "expireTimeStamp": PINNED_EXPIRE,
    }


def test_psign_is_hs256_jwt_verifiable_with_play_key() -> None:
    """HMAC-SHA256 signature verifies against the PlayKey."""
    token = build_player_psign(
        app_id=OFFICIAL_APP_ID,
        file_id=OFFICIAL_FILE_ID,
        play_key=OFFICIAL_PLAY_KEY,
        current_time=PINNED_CURRENT,
        expire_time=PINNED_EXPIRE,
    )
    header_b64, payload_b64, signature_b64 = token.split(".")
    header = json.loads(_b64url_decode(header_b64))
    payload = json.loads(_b64url_decode(payload_b64))
    assert header == JWT_HEADER
    assert payload["appId"] == OFFICIAL_APP_ID
    assert payload["fileId"] == OFFICIAL_FILE_ID
    expected = hmac.new(
        OFFICIAL_PLAY_KEY.encode("utf-8"),
        f"{header_b64}.{payload_b64}".encode("ascii"),
        hashlib.sha256,
    ).digest()
    padding = "=" * (-len(signature_b64) % 4)
    assert base64.urlsafe_b64decode(signature_b64 + padding) == expected


def test_psign_is_deterministic_for_pinned_timestamps() -> None:
    """Pinned timestamps produce a stable compact JWT."""
    first = sign_psign(
        build_psign_payload(
            OFFICIAL_APP_ID,
            OFFICIAL_FILE_ID,
            PINNED_CURRENT,
            PINNED_EXPIRE,
        ),
        OFFICIAL_PLAY_KEY,
    )
    second = build_player_psign(
        OFFICIAL_APP_ID,
        OFFICIAL_FILE_ID,
        OFFICIAL_PLAY_KEY,
        PINNED_CURRENT,
        PINNED_EXPIRE,
    )
    assert first == second
    assert compact_json_bytes(JWT_HEADER) == b'{"alg":"HS256","typ":"JWT"}'
