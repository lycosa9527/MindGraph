"""Resolve /auth login heroes from COS or local silent reencodes."""

from __future__ import annotations

from pathlib import Path

from config.settings import config
from scripts.auth_login_video.paths import DESKTOP_DIR, SHIPPED_HERO, WORK_DIR
from services.auth.login_hero_clips import parse_hero_clip_id
from services.infrastructure.utils.spa_handler import is_dev_mode
from services.utils.tencent_cos_client import (
    cos_credentials_configured,
    cos_object_key,
    generate_presigned_get_url,
)

HERO_CACHE = {"Cache-Control": "private, max-age=120"}


def local_hero_path(clip_id: str) -> Path | None:
    """Desktop reencode, work reencode, then the shipped 01 fallback."""
    packed = parse_hero_clip_id(clip_id)
    desktop = DESKTOP_DIR / f"{packed}-reencode.mp4"
    if desktop.is_file() and desktop.stat().st_size > 10000:
        return desktop
    work = WORK_DIR / f"{packed}-wan3-reencode.mp4"
    if work.is_file() and work.stat().st_size > 10000:
        return work
    if packed == "01-awaken-cosmos" and SHIPPED_HERO.is_file() and SHIPPED_HERO.stat().st_size > 10000:
        return SHIPPED_HERO
    return None


def hero_presigned_url(clip_id: str) -> str | None:
    """Short-lived COS GET URL. Local Vite cannot pull COS, so skip in dev."""
    if is_dev_mode():
        return None
    if not config.COS_AUTH_LOGIN_ENABLED or not cos_credentials_configured():
        return None
    packed = parse_hero_clip_id(clip_id)
    object_key = cos_object_key(f"{packed}.mp4", prefix=config.COS_AUTH_LOGIN_PREFIX)
    return generate_presigned_get_url(
        object_key,
        expired=config.COS_AUTH_LOGIN_PRESIGN_GET_TTL,
    )
