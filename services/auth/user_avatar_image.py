"""Store a user's photo avatar on Tencent COS and remember its public URL.

The browser loads that URL directly. Presigned URLs are not stored.
"""

from __future__ import annotations

import os
import time
from io import BytesIO
from urllib.parse import quote, unquote, urlparse

from PIL import Image, ImageDraw, ImageOps, UnidentifiedImageError
from PIL.Image import DecompressionBombError

from config.cos_env_prefix import cos_feature_prefix
from services.utils.tencent_cos_client import (
    COS_BUCKET,
    COS_REGION,
    cos_credentials_configured,
    cos_object_key,
    delete_object,
    upload_bytes,
)
from utils.user_avatar_defaults import DEFAULT_USER_AVATAR_EMOJI

AVATAR_SIDE_PX = 512
AVATAR_MAX_UPLOAD_BYTES = 4 * 1024 * 1024
_AVATAR_FEATURE = "avatars"


class AvatarImageError(Exception):
    """Rejected or unstorable user avatar image."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def avatar_photos_enabled() -> bool:
    """Photo URLs are for deployed hosts. Local dev stays on emoji."""
    env = os.getenv("ENVIRONMENT", "production").strip().lower()
    return env not in {"development", "dev"}


def avatar_for_client(value: str | None) -> str:
    """Emoji for local dev, even when the row still holds a COS URL."""
    stored = (value or "").strip()
    if not stored:
        return DEFAULT_USER_AVATAR_EMOJI
    if not avatar_photos_enabled() and stored.lower().startswith(("http://", "https://")):
        return DEFAULT_USER_AVATAR_EMOJI
    return stored


def user_avatar_object_key(user_id: int) -> str:
    """Stable object key for one user's photo. A new upload overwrites it."""
    prefix = cos_feature_prefix(_AVATAR_FEATURE)
    return cos_object_key(f"users/{user_id}.png", prefix=prefix)


def public_avatar_url(object_key: str) -> str | None:
    """Virtual-host URL the browser can load without an app proxy."""
    if not COS_BUCKET or not COS_REGION:
        return None
    encoded = quote(object_key.lstrip("/"), safe="/")
    return f"https://{COS_BUCKET}.cos.{COS_REGION}.myqcloud.com/{encoded}"


def stored_avatar_object_key(value: str | None) -> str | None:
    """Return the COS key when ``value`` is one of our public avatar URLs."""
    if not value or not COS_BUCKET or not COS_REGION:
        return None
    parsed = urlparse(value.strip())
    host = f"{COS_BUCKET}.cos.{COS_REGION}.myqcloud.com"
    if parsed.scheme != "https" or parsed.netloc != host:
        return None
    key = unquote(parsed.path.lstrip("/"))
    prefix = cos_feature_prefix(_AVATAR_FEATURE).strip("/") + "/"
    if not key.startswith(prefix) or not key.endswith(".png"):
        return None
    return key


def release_replaced_avatar(previous: str | None, current: str | None) -> None:
    """Delete the previous photo when the user switches back to an emoji."""
    previous_key = stored_avatar_object_key(previous)
    if previous_key is None or previous_key == stored_avatar_object_key(current):
        return
    delete_object(previous_key)


def normalize_avatar_png(data: bytes) -> bytes:
    """Center-crop, resize to 512, and punch a circular alpha mask."""
    if not data:
        raise AvatarImageError("empty")
    if len(data) > AVATAR_MAX_UPLOAD_BYTES:
        raise AvatarImageError("too_large")
    try:
        with Image.open(BytesIO(data)) as opened:
            oriented = ImageOps.exif_transpose(opened) or opened
            frame = oriented.convert("RGBA")
    except (UnidentifiedImageError, DecompressionBombError, OSError, ValueError) as exc:
        raise AvatarImageError("invalid") from exc
    if frame.width < 1 or frame.height < 1:
        raise AvatarImageError("invalid")
    if frame.width > 4096 or frame.height > 4096:
        frame.thumbnail((4096, 4096), Image.Resampling.LANCZOS)
    side = min(frame.width, frame.height)
    left = (frame.width - side) // 2
    top = (frame.height - side) // 2
    square = frame.crop((left, top, left + side, top + side))
    resized = square.resize((AVATAR_SIDE_PX, AVATAR_SIDE_PX), Image.Resampling.LANCZOS)
    mask = Image.new("L", (AVATAR_SIDE_PX, AVATAR_SIDE_PX), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, AVATAR_SIDE_PX - 1, AVATAR_SIDE_PX - 1), fill=255)
    resized.putalpha(mask)
    output = BytesIO()
    resized.save(output, format="PNG", optimize=True)
    return output.getvalue()


def publish_user_avatar_png(user_id: int, data: bytes) -> str:
    """Upload a public-read PNG and return a cache-busted COS URL."""
    png = normalize_avatar_png(data)
    if not cos_credentials_configured():
        raise AvatarImageError("unavailable")
    key = user_avatar_object_key(user_id)
    uploaded = upload_bytes(
        png,
        key,
        content_type="image/png",
        acl="public-read",
        log_prefix="[Avatar]",
    )
    if not uploaded:
        raise AvatarImageError("unavailable")
    base = public_avatar_url(key)
    if not base:
        raise AvatarImageError("unavailable")
    return f"{base}?v={int(time.time())}"
