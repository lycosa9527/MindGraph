"""Learning Space instruction images: COS first, local disk only when COS is off.

Postgres stores short refs (``lsimg:<logical_key>``), never image bytes.
"""

from __future__ import annotations

import base64
import binascii
import logging
import re
from datetime import UTC, datetime
from collections.abc import Sequence
from pathlib import Path
from typing import Optional
from uuid import uuid4

from config.settings import config
from services.utils.tencent_cos_client import (
    cos_credentials_configured,
    cos_object_key,
    delete_object,
    generate_presigned_get_url,
    get_object_bytes,
    upload_bytes,
)

logger = logging.getLogger(__name__)

STORAGE_COS = "cos"
STORAGE_LOCAL = "local"
IMAGE_REF_PREFIX = "lsimg:"
MAX_IMAGE_BYTES = 2 * 1024 * 1024
_DATA_URL_RE = re.compile(r"^data:(image/(?:png|jpe?g|webp|gif));base64,(.+)$", re.IGNORECASE | re.DOTALL)
_ALLOWED_TYPES = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


def cos_learning_space_enabled() -> bool:
    """True when Learning Space COS storage is on and credentials exist."""
    if not config.COS_LEARNING_SPACE_ENABLED:
        return False
    return cos_credentials_configured()


def storage_backend() -> str:
    """Active byte store: cos | local."""
    return STORAGE_COS if cos_learning_space_enabled() else STORAGE_LOCAL


def assert_safe_logical_key(logical_key: str) -> str:
    """Reject empty keys and path traversal."""
    cleaned = logical_key.strip().lstrip("/")
    if not cleaned or ".." in cleaned.split("/"):
        raise ValueError("Invalid image key")
    return cleaned


def build_logical_key(*, owner_id: int, filename: str) -> str:
    """Year/month key namespaced by uploader. No COS host in the string."""
    now = datetime.now(UTC)
    raw_name = Path(filename or "image").name
    suffix = Path(raw_name).suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        suffix = ".jpg"
    if suffix == ".jpeg":
        suffix = ".jpg"
    return f"{int(owner_id)}/{now.year}/{now.month:02d}/{uuid4().hex[:12]}{suffix}"


def full_learning_space_cos_key(logical_key: str) -> str:
    """Bucket key under COS_LEARNING_SPACE_PREFIX."""
    return cos_object_key(assert_safe_logical_key(logical_key), prefix=config.COS_LEARNING_SPACE_PREFIX)


def local_root() -> Path:
    """Local fallback root when COS is off (dev/CI)."""
    return Path("static") / "learning_space" / "images"


def local_path_for_key(logical_key: str) -> Path:
    """Map a logical key onto the local fallback tree."""
    key = assert_safe_logical_key(logical_key)
    candidate = (local_root() / key).resolve()
    root = local_root().resolve()
    if not candidate.is_relative_to(root):
        raise ValueError("Invalid image key")
    return candidate


def is_image_ref(value: str) -> bool:
    """True for stored COS/local refs (not data URLs or absolute http)."""
    item = (value or "").strip()
    if not item:
        return False
    if item.startswith(IMAGE_REF_PREFIX):
        return True
    if item.startswith("data:") or item.startswith("http://") or item.startswith("https://"):
        return False
    return "/" in item and ".." not in item


def logical_key_from_ref(value: str) -> Optional[str]:
    """Extract the logical key from an ``lsimg:`` ref or a bare key."""
    item = (value or "").strip()
    if not item:
        return None
    if item.startswith("data:") or item.startswith("http://") or item.startswith("https://"):
        return None
    if item.startswith(IMAGE_REF_PREFIX):
        item = item[len(IMAGE_REF_PREFIX) :]
    try:
        return assert_safe_logical_key(item)
    except ValueError:
        return None


def ref_for_key(logical_key: str) -> str:
    """Persistable short ref for a logical key."""
    return f"{IMAGE_REF_PREFIX}{assert_safe_logical_key(logical_key)}"


def public_image_src(stored: str, *, assignment_id: int | None, index: int) -> str:
    """Stable API src for ``<img>``. Presigned COS URLs stay on the download hop."""
    item = (stored or "").strip()
    if not item:
        return ""
    if item.startswith("data:") or item.startswith("http://") or item.startswith("https://"):
        return item
    if assignment_id is None:
        return item
    return f"/api/learning-space/instruction-images/{int(assignment_id)}/{int(index)}"


def public_instruction_images(stored: Sequence[object] | None, *, assignment_id: int | None) -> list[str]:
    """Serialize stored refs/URLs for API responses (max 6)."""
    if not isinstance(stored, list):
        return []
    out: list[str] = []
    for index, raw in enumerate(stored):
        if not isinstance(raw, str):
            continue
        src = public_image_src(raw, assignment_id=assignment_id, index=index)
        if src:
            out.append(src)
        if len(out) >= 6:
            break
    return out


def stored_image_keys(stored: Sequence[object] | None) -> list[str]:
    """Logical keys that should be deleted with the assignment."""
    if not isinstance(stored, list):
        return []
    keys: list[str] = []
    for raw in stored:
        if not isinstance(raw, str):
            continue
        key = logical_key_from_ref(raw)
        if key:
            keys.append(key)
    return keys


def detect_image_content_type(data: bytes) -> str | None:
    """Return image/* from magic bytes; reject HTML or other disguises."""
    if len(data) < 12:
        return None
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def put_image_bytes_sync(logical_key: str, data: bytes, content_type: str) -> str:
    """Write bytes to COS or local disk. Returns the persistable ref."""
    key = assert_safe_logical_key(logical_key)
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError("instruction image too large")
    detected = detect_image_content_type(data)
    if detected is None:
        raise ValueError("Unsupported image type")
    declared = (content_type or "").split(";")[0].strip().lower()
    if declared == "image/jpg":
        declared = "image/jpeg"
    content_type = detected if declared != detected else declared
    if storage_backend() == STORAGE_COS:
        uploaded = upload_bytes(
            data,
            full_learning_space_cos_key(key),
            content_type=content_type,
            log_prefix="[LearningSpace/COS]",
        )
        if not uploaded:
            raise ValueError("Could not store image on COS")
        return ref_for_key(key)
    path = local_path_for_key(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return ref_for_key(key)


def decode_data_url(data_url: str) -> tuple[bytes, str] | None:
    """Decode a ``data:image/...;base64,...`` payload."""
    match = _DATA_URL_RE.match((data_url or "").strip())
    if match is None:
        return None
    mime = match.group(1).lower()
    if mime == "image/jpg":
        mime = "image/jpeg"
    if mime not in _ALLOWED_TYPES:
        return None
    try:
        payload = base64.b64decode(match.group(2), validate=True)
    except (binascii.Error, ValueError):
        return None
    if not payload or len(payload) > MAX_IMAGE_BYTES:
        return None
    return payload, mime


def persist_instruction_images_sync(raw_items: list[str], *, owner_id: int) -> list[str]:
    """Store new data-URL images on COS; keep existing refs/URLs."""
    stored: list[str] = []
    for raw in raw_items:
        item = (raw or "").strip()
        if not item:
            continue
        if is_image_ref(item) or item.startswith("http://") or item.startswith("https://"):
            if item.startswith("http://") or item.startswith("https://"):
                if len(item) > 2000:
                    raise ValueError("instruction image too large")
                stored.append(item)
            else:
                key = logical_key_from_ref(item)
                if key is None:
                    raise ValueError("Invalid image key")
                stored.append(ref_for_key(key))
        else:
            decoded = decode_data_url(item)
            if decoded is None:
                raise ValueError("instruction image too large")
            payload, mime = decoded
            suffix = _ALLOWED_TYPES[mime]
            key = build_logical_key(owner_id=owner_id, filename=f"upload{suffix}")
            stored.append(put_image_bytes_sync(key, payload, mime))
        if len(stored) >= 6:
            break
    return stored


def delete_stored_images_sync(keys: list[str]) -> None:
    """Best-effort delete of COS/local objects."""
    for key in keys:
        try:
            safe = assert_safe_logical_key(key)
        except ValueError:
            continue
        if cos_learning_space_enabled():
            delete_object(full_learning_space_cos_key(safe))
        try:
            path = local_path_for_key(safe)
        except ValueError:
            continue
        if path.is_file():
            path.unlink()


def read_image_bytes_sync(logical_key: str) -> tuple[bytes, str] | None:
    """Load image bytes for the download hop (COS or local)."""
    key = assert_safe_logical_key(logical_key)
    suffix = Path(key).suffix.lower()
    content_type = "image/jpeg"
    if suffix == ".png":
        content_type = "image/png"
    elif suffix == ".webp":
        content_type = "image/webp"
    elif suffix == ".gif":
        content_type = "image/gif"
    if cos_learning_space_enabled():
        payload = get_object_bytes(full_learning_space_cos_key(key), log_prefix="[LearningSpace/COS]")
        if payload:
            return payload, content_type
    try:
        path = local_path_for_key(key)
    except ValueError:
        return None
    if not path.is_file():
        return None
    return path.read_bytes(), content_type


def create_presigned_get(logical_key: str) -> Optional[str]:
    """Short-TTL COS GET URL, or None when COS is off."""
    if not cos_learning_space_enabled():
        return None
    return generate_presigned_get_url(
        full_learning_space_cos_key(logical_key),
        expired=int(getattr(config, "COS_LEARNING_SPACE_PRESIGN_GET_TTL", 300) or 300),
    )
