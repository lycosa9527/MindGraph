"""Tencent VOD client upload signature (HMAC-SHA1 + Base64).

Spec: https://cloud.tencent.com/document/product/266/9221
Example: https://cloud.tencent.com/document/product/266/10638

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from typing import Optional
from urllib.parse import urlencode

MAX_UPLOAD_TTL_SECONDS = 7776000
RANDOM_MAX = 4294967295


def build_upload_original(
    secret_id: str,
    current_time: int,
    expire_time: int,
    random_value: int,
    procedure: str = "",
    vod_sub_app_id: Optional[int] = None,
    one_time_valid: int = 1,
    source_context: str = "",
    class_id: int = 0,
) -> str:
    """Build the official QueryString plaintext (required keys first)."""
    parts: list[tuple[str, str]] = [
        ("secretId", secret_id),
        ("currentTimeStamp", str(int(current_time))),
        ("expireTime", str(int(expire_time))),
        ("random", str(int(random_value))),
    ]
    if one_time_valid:
        parts.append(("oneTimeValid", str(int(one_time_valid))))
    if class_id:
        parts.append(("classId", str(int(class_id))))
    if procedure:
        parts.append(("procedure", procedure))
    if vod_sub_app_id is not None:
        parts.append(("vodSubAppId", str(int(vod_sub_app_id))))
    if source_context:
        parts.append(("sourceContext", source_context))
    return urlencode(parts)


def sign_upload_original(original: str, secret_key: str) -> str:
    """HMAC-SHA1(original) || original, then standard Base64."""
    digest = hmac.new(
        secret_key.encode("utf-8"),
        original.encode("utf-8"),
        hashlib.sha1,
    ).digest()
    merged = digest + original.encode("utf-8")
    return base64.b64encode(merged).decode("ascii")


def clamp_upload_ttl(ttl_seconds: int) -> int:
    """Clamp upload signature lifetime to the official 90-day maximum."""
    ttl = int(ttl_seconds)
    if ttl < 1:
        return 1
    if ttl > MAX_UPLOAD_TTL_SECONDS:
        return MAX_UPLOAD_TTL_SECONDS
    return ttl


def new_upload_random() -> int:
    """32-bit unsigned random used once per oneTimeValid signature."""
    return secrets.randbelow(RANDOM_MAX + 1)


def build_client_upload_signature(
    secret_id: str,
    secret_key: str,
    current_time: int,
    expire_time: int,
    random_value: int,
    procedure: str = "",
    vod_sub_app_id: Optional[int] = None,
    one_time_valid: int = 1,
    source_context: str = "",
    class_id: int = 0,
) -> str:
    """Return the Base64 client upload signature."""
    original = build_upload_original(
        secret_id=secret_id,
        current_time=current_time,
        expire_time=expire_time,
        random_value=random_value,
        procedure=procedure,
        vod_sub_app_id=vod_sub_app_id,
        one_time_valid=one_time_valid,
        source_context=source_context,
        class_id=class_id,
    )
    return sign_upload_original(original, secret_key)
