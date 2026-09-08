"""Load Tencent Cloud VOD credentials from env.

SecretId/SecretKey reuse TENCENT_SMS_SECRET_* when VOD-specific keys are unset.
PlayKey is the default-distribution 播放密钥, not KEY 防盗链.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from config.settings import config


class TencentVodNotConfiguredError(RuntimeError):
    """VOD AppId, PlayKey, or CAM keys are missing."""


@dataclass(frozen=True)
class TencentVodCredentials:
    """CAM keys plus VOD application PlayKey."""

    app_id: int
    secret_id: str
    secret_key: str
    play_key: str
    region: str
    license_url: str
    license_key: str
    procedure: str
    psign_ttl: int
    upload_ttl: int
    adaptive_definition: int


def _env_or_sms(vod_key: str, sms_key: str) -> str:
    """Prefer a VOD-specific env var, else the shared SMS CAM key."""
    specific = os.getenv(vod_key, "").strip()
    if specific:
        return specific
    return os.getenv(sms_key, "").strip()


def load_tencent_vod_credentials() -> TencentVodCredentials:
    """Load VOD credentials; raise when required fields are empty."""
    raw_app_id = config.TENCENT_VOD_APP_ID
    play_key = config.TENCENT_VOD_PLAY_KEY
    secret_id = _env_or_sms("TENCENT_VOD_SECRET_ID", "TENCENT_SMS_SECRET_ID")
    secret_key = _env_or_sms("TENCENT_VOD_SECRET_KEY", "TENCENT_SMS_SECRET_KEY")
    if not raw_app_id or not play_key or not secret_id or not secret_key:
        raise TencentVodNotConfiguredError(
            "Tencent VOD is not configured (TENCENT_VOD_APP_ID, "
            "TENCENT_VOD_PLAY_KEY, and CAM SecretId/SecretKey are required)"
        )
    try:
        app_id = int(raw_app_id)
    except ValueError as exc:
        raise TencentVodNotConfiguredError(f"Invalid TENCENT_VOD_APP_ID: {raw_app_id!r}") from exc
    if app_id <= 0:
        raise TencentVodNotConfiguredError(f"Invalid TENCENT_VOD_APP_ID: {raw_app_id!r}")
    return TencentVodCredentials(
        app_id=app_id,
        secret_id=secret_id,
        secret_key=secret_key,
        play_key=play_key,
        region=config.TENCENT_VOD_REGION,
        license_url=config.TENCENT_VOD_LICENSE_URL,
        license_key=config.TENCENT_VOD_LICENSE_KEY,
        procedure=config.TENCENT_VOD_PROCEDURE,
        psign_ttl=config.TENCENT_VOD_PSIGN_TTL,
        upload_ttl=config.TENCENT_VOD_UPLOAD_TTL,
        adaptive_definition=config.TENCENT_VOD_ADAPTIVE_DEFINITION,
    )


def vod_credentials_configured() -> bool:
    """True when AppId, PlayKey, and CAM keys are present and valid."""
    try:
        load_tencent_vod_credentials()
    except TencentVodNotConfiguredError:
        return False
    return True
