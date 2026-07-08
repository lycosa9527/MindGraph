"""
Case Square helpers: thumbnail, spec, and storage.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import json
import logging
import uuid
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, Request, UploadFile, status

from routers.features.community_helpers import (
    PNG_MAGIC,
    SPEC_MAX_BYTES,
    THUMBNAIL_MAX_BYTES,
    parse_spec_json,
)

logger = logging.getLogger(__name__)

CASE_SQUARE_DIR = Path("static/case_square")
CASE_SQUARE_DIR.mkdir(parents=True, exist_ok=True)

ATTACHMENT_MAX_BYTES = 20 * 1024 * 1024
VIDEO_MAX_BYTES = 100 * 1024 * 1024
ALLOWED_DOC_SUFFIXES = frozenset({".doc", ".docx", ".pdf"})
ALLOWED_SOURCE_SUFFIXES = frozenset({".mg", ".png", ".jpg", ".jpeg", ".webp", ".gif"})
GALLERY_IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".webp", ".gif"})
GALLERY_MAX_ITEMS = 12
ALLOWED_VIDEO_SUFFIXES = frozenset({".mp4", ".webm", ".mov", ".m4v"})


def _validate_thumbnail(content: bytes) -> None:
    if len(content) > THUMBNAIL_MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Thumbnail too large. Max 2MB, got {len(content) / 1024 / 1024:.1f}MB",
        )
    if not content.startswith(PNG_MAGIC):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid PNG file format",
        )


def _suffix_or_raise(filename: Optional[str], allowed: frozenset[str]) -> str:
    suffix = Path(filename or "").suffix.lower()
    if suffix not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Allowed: {sorted(allowed)}",
        )
    return suffix


def save_thumbnail(post_id: str, content: bytes) -> str:
    path = CASE_SQUARE_DIR / f"{post_id}.png"
    path.write_bytes(content)
    return f"case_square/{post_id}.png"


async def save_thumbnail_from_upload(post_id: str, thumbnail: UploadFile) -> str:
    content = await thumbnail.read()
    _validate_thumbnail(content)
    return save_thumbnail(post_id, content)


def _gallery_file_exists(rel_path: str) -> bool:
    normalized = rel_path.lstrip("/").replace("\\", "/")
    if not normalized.startswith("case_square/"):
        return False
    return (Path("static") / normalized).is_file()


def resolve_gallery_image_storage_path(post_id: str, slot: int, entry: dict) -> str | None:
    """Return stored relative path for a gallery image (spec path or on-disk slot file)."""
    path = entry.get("path")
    if isinstance(path, str) and path.strip():
        rel = path.lstrip("/")
        if _gallery_file_exists(rel):
            return rel

    for ext in GALLERY_IMAGE_SUFFIXES:
        rel = f"case_square/{post_id}_gallery_{slot}{ext}"
        if _gallery_file_exists(rel):
            return rel

    filename = entry.get("filename")
    if isinstance(filename, str) and filename.strip():
        for candidate in (
            f"case_square/{filename}",
            f"case_square/{post_id}_{filename}",
        ):
            if _gallery_file_exists(candidate):
                return candidate

    return None


def count_pending_gallery_images(spec_obj: dict) -> int:
    gallery = spec_obj.get("gallery")
    if not isinstance(gallery, list):
        return 0
    return sum(1 for item in gallery if isinstance(item, dict) and item.get("kind") == "image" and not item.get("path"))


def assert_gallery_uploads_resolved(spec_obj: dict) -> None:
    """Reject saves that still have image slots without a stored path."""
    pending = count_pending_gallery_images(spec_obj)
    if pending:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Gallery image uploads incomplete; please retry publishing",
        )


def gallery_uploads_from_binding(bound: list[UploadFile]) -> list[UploadFile]:
    """Return non-empty gallery file parts from FastAPI File() binding."""
    return [upload for upload in bound if getattr(upload, "filename", None)]


from starlette.datastructures import UploadFile as StarletteUploadFile


def _form_upload_file(value: object) -> StarletteUploadFile | None:
    if not isinstance(value, StarletteUploadFile):
        return None
    if not value.filename:
        return None
    return value


async def collect_gallery_images_from_request(request: Request) -> list[UploadFile]:
    """Read all gallery_images parts from multipart (reliable vs mixed Form+File binding)."""
    form = await request.form()
    images: list[UploadFile] = []
    for value in form.getlist("gallery_images"):
        upload = _form_upload_file(value)
        if upload is not None:
            images.append(upload)
    if images:
        return images
    for key, value in form.multi_items():
        if key != "gallery_images":
            continue
        upload = _form_upload_file(value)
        if upload is not None:
            images.append(upload)
    return images


async def resolve_gallery_image_uploads(
    bound: list[UploadFile],
    request: Request,
) -> list[UploadFile]:
    """Prefer File() binding; fall back to parsing multipart when binding is empty."""
    from_binding = gallery_uploads_from_binding(bound)
    if from_binding:
        return from_binding
    return await collect_gallery_images_from_request(request)


async def apply_gallery_image_uploads(
    post_id: str,
    spec_obj: dict,
    gallery_images: list[UploadFile],
) -> None:
    """Attach uploaded gallery image files to spec gallery items (pending slots only)."""
    gallery = spec_obj.get("gallery")
    if not isinstance(gallery, list):
        return
    if not gallery_images:
        return
    upload_idx = 0
    for slot, item in enumerate(gallery):
        if not isinstance(item, dict) or item.get("kind") != "image":
            continue
        if item.get("path"):
            continue
        if upload_idx >= len(gallery_images):
            logger.warning(
                "[CaseSquare] Missing gallery upload for post=%s slot=%s (need %s more)",
                post_id,
                slot,
                count_pending_gallery_images(spec_obj),
            )
            break
        upload = gallery_images[upload_idx]
        upload_idx += 1
        if not upload.filename:
            logger.warning("[CaseSquare] Gallery upload missing filename post=%s slot=%s", post_id, slot)
            continue
        path = await save_case_file(
            post_id,
            upload,
            GALLERY_IMAGE_SUFFIXES,
            f"gallery_{slot}",
            ATTACHMENT_MAX_BYTES,
        )
        item["path"] = path
        item["filename"] = Path(upload.filename).name
        item.pop("pending", None)
    spec_obj["source"] = "gallery"


def validate_gallery_spec(spec_obj: dict) -> None:
    """Ensure diagram_case gallery payload is well-formed."""
    gallery = spec_obj.get("gallery")
    if gallery is None:
        return
    if not isinstance(gallery, list):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="gallery must be a JSON array",
        )
    if len(gallery) > GALLERY_MAX_ITEMS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"At most {GALLERY_MAX_ITEMS} gallery items allowed",
        )
    for item in gallery:
        if not isinstance(item, dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="gallery items must be objects",
            )
        kind = item.get("kind")
        if kind == "image":
            if not item.get("path") and not item.get("pending"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="image gallery items require path or pending upload",
                )
        elif kind == "diagram":
            if not item.get("diagram_id"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="diagram gallery items require diagram_id",
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="gallery item kind must be image or diagram",
            )


async def save_case_file(
    post_id: str,
    upload: UploadFile,
    allowed_suffixes: frozenset[str],
    name_prefix: str,
    max_bytes: int,
) -> str:
    content = await upload.read()
    suffix = _suffix_or_raise(upload.filename, allowed_suffixes)
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Max {max_bytes // 1024 // 1024}MB",
        )
    rel_name = f"{post_id}_{name_prefix}{suffix}"
    path = CASE_SQUARE_DIR / rel_name
    path.write_bytes(content)
    return f"case_square/{rel_name}"


def save_spec_json(post_id: str, spec_obj: dict) -> None:
    path = CASE_SQUARE_DIR / f"{post_id}.json"
    try:
        path.write_text(json.dumps(spec_obj, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as err:
        logger.warning("[CaseSquare] Failed to save spec JSON %s: %s", path, err)


def delete_thumbnail(post_id: str) -> None:
    path = CASE_SQUARE_DIR / f"{post_id}.png"
    if path.exists():
        try:
            path.unlink()
        except OSError as err:
            logger.warning("[CaseSquare] Failed to delete thumbnail %s: %s", path, err)


def delete_spec_json(post_id: str) -> None:
    path = CASE_SQUARE_DIR / f"{post_id}.json"
    if path.exists():
        try:
            path.unlink()
        except OSError as err:
            logger.warning("[CaseSquare] Failed to delete spec JSON %s: %s", path, err)


def delete_case_file(rel_path: str) -> None:
    """Delete a stored case attachment/video under static/ (best-effort)."""
    normalized = rel_path.lstrip("/").replace("\\", "/")
    if not normalized.startswith("case_square/"):
        logger.warning("[CaseSquare] Refusing to delete path outside case_square: %s", rel_path)
        return
    path = Path("static") / normalized
    if path.exists():
        try:
            path.unlink()
        except OSError as err:
            logger.warning("[CaseSquare] Failed to delete case file %s: %s", path, err)


def prepare_post_id_and_spec(spec: str) -> tuple[str, dict]:
    if len(spec.encode("utf-8")) > SPEC_MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Diagram spec too large",
        )
    return str(uuid.uuid4()), parse_spec_json(spec)


def parse_tags_json(tags: str) -> list[str]:
    if not tags or not tags.strip():
        return []
    try:
        parsed = json.loads(tags)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid tags JSON: {exc}",
        ) from exc
    if not isinstance(parsed, list):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tags must be a JSON array of strings",
        )
    normalized: list[str] = []
    for item in parsed:
        if not isinstance(item, str):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tags must be a JSON array of strings",
            )
        tag = item.strip()
        if tag and tag not in normalized:
            normalized.append(tag[:50])
    return normalized[:20]
