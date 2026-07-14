"""
Showcase helpers: thumbnail, spec, and storage.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import json
import logging
import uuid
from pathlib import Path
from typing import Optional, cast

from fastapi import HTTPException, Request, UploadFile, status
from starlette.datastructures import UploadFile as StarletteUploadFile

from routers.features.community.helpers import (
    PNG_MAGIC,
    SPEC_MAX_BYTES,
    THUMBNAIL_MAX_BYTES,
    parse_spec_json,
)
from services.showcase.storage import (
    build_object_key,
    delete_key_sync,
    is_showcase_logical_key,
    local_path_for_key,
    put_bytes,
    put_bytes_sync,
    showcase_public_asset_url as storage_public_asset_url,
)

logger = logging.getLogger(__name__)

SHOWCASE_DIR = Path("static/case_square")
SHOWCASE_DIR.mkdir(parents=True, exist_ok=True)

ATTACHMENT_MAX_BYTES = 20 * 1024 * 1024
VIDEO_MAX_BYTES = 100 * 1024 * 1024
ALLOWED_DOC_SUFFIXES = frozenset({".doc", ".docx", ".pdf"})
ALLOWED_SOURCE_SUFFIXES = frozenset({".mg", ".png", ".jpg", ".jpeg", ".webp", ".gif"})
GALLERY_IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".webp", ".gif"})
GALLERY_MAX_ITEMS = 12
ALLOWED_VIDEO_SUFFIXES = frozenset({".mp4", ".webm", ".mov", ".m4v"})

PDF_MAGIC = b"%PDF"
JPEG_MAGIC = b"\xff\xd8\xff"
GIF_MAGIC_87A = b"GIF87a"
GIF_MAGIC_89A = b"GIF89a"
WEBP_RIFF = b"RIFF"
WEBP_WEBP = b"WEBP"
ZIP_LOCAL_FILE_HEADER = b"PK\x03\x04"
ZIP_EMPTY = b"PK\x05\x06"
_ISO_BMFF_FTYP = b"ftyp"
WEBM_EBML = b"\x1a\x45\xdf\xa3"
MG_JSON_STARTS = (b"{", b"[")
OLE_COMPOUND_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


def showcase_public_asset_url(rel_path: str) -> str:
    """Build authenticated asset URL for a stored Showcase relative path."""
    return storage_public_asset_url(rel_path)


def post_id_from_showcase_asset_path(asset_path: str) -> str | None:
    """Extract post UUID from new or legacy asset path."""
    normalized = asset_path.lstrip("/").replace("\\", "/")
    # New: showcase/posts/{uuid}/role.ext
    if normalized.startswith("showcase/posts/"):
        parts = normalized.split("/")
        if len(parts) >= 3:
            candidate = parts[2]
            try:
                uuid.UUID(candidate)
            except ValueError:
                return None
            return candidate
    # Legacy: case_square/{uuid}_doc.pdf or case_square/{uuid}.png
    name = Path(normalized).name
    return post_id_from_showcase_filename(name)


def post_id_from_showcase_filename(filename: str) -> str | None:
    """Extract post UUID from ``{uuid}`` or ``{uuid}_suffix`` asset names."""
    name = Path(filename).name
    if len(name) < 36:
        return None
    candidate = name[:36]
    try:
        uuid.UUID(candidate)
    except ValueError:
        return None
    if len(name) > 36 and name[36] not in "._":
        return None
    return candidate


def resolve_showcase_disk_path(rel_path: str) -> Path:
    """Resolve a stored relative path under static showcase dirs with traversal checks."""
    normalized = rel_path.lstrip("/").replace("\\", "/")
    if not is_showcase_logical_key(normalized):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    try:
        candidate = local_path_for_key(normalized)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from exc
    if not candidate.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return candidate


def _validate_magic_bytes(content: bytes, suffix: str) -> None:
    """Reject uploads whose content does not match the declared suffix."""
    if suffix == ".png":
        if not content.startswith(PNG_MAGIC):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid PNG file format")
        return
    if suffix in {".jpg", ".jpeg"}:
        if not content.startswith(JPEG_MAGIC):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JPEG file format")
        return
    if suffix == ".gif":
        if not (content.startswith(GIF_MAGIC_87A) or content.startswith(GIF_MAGIC_89A)):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid GIF file format")
        return
    if suffix == ".webp":
        if len(content) < 12 or not content.startswith(WEBP_RIFF) or content[8:12] != WEBP_WEBP:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid WebP file format")
        return
    if suffix == ".pdf":
        if not content.startswith(PDF_MAGIC):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid PDF file format")
        return
    if suffix == ".docx":
        if not (content.startswith(ZIP_LOCAL_FILE_HEADER) or content.startswith(ZIP_EMPTY)):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid DOCX file format")
        return
    if suffix == ".doc":
        if not content.startswith(OLE_COMPOUND_MAGIC):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid DOC file format")
        return
    if suffix in {".mp4", ".m4v", ".mov"}:
        if len(content) < 8 or content[4:8] != _ISO_BMFF_FTYP:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid video file format")
        return
    if suffix == ".webm":
        if not content.startswith(WEBM_EBML):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid WebM file format")
        return
    if suffix == ".mg":
        stripped = content.lstrip()
        if not stripped or stripped[:1] not in MG_JSON_STARTS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid MindGraph source format",
            )
        return
    if suffix == ".json":
        stripped = content.lstrip()
        if not stripped or stripped[:1] not in MG_JSON_STARTS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid JSON file format",
            )
        return
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Unsupported file type for validation: {suffix}",
    )


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
    """Write PNG thumbnail bytes and return the stored logical key (sync helper)."""

    _validate_thumbnail(content)
    logical_key = build_object_key(post_id, "thumbnail", ".png")
    put_bytes_sync(logical_key, content)
    return logical_key


async def save_thumbnail_from_upload(post_id: str, thumbnail: UploadFile) -> str:
    """Validate and persist an uploaded thumbnail for a post."""

    content = await thumbnail.read()
    _validate_thumbnail(content)
    logical_key = build_object_key(post_id, "thumbnail", ".png")
    await put_bytes(logical_key, content)
    return logical_key


def _gallery_file_exists(rel_path: str) -> bool:

    normalized = rel_path.lstrip("/").replace("\\", "/")
    if not is_showcase_logical_key(normalized):
        return False
    try:
        return local_path_for_key(normalized).is_file()
    except ValueError:
        return False


def resolve_gallery_image_storage_path(post_id: str, slot: int, entry: dict) -> str | None:
    """Return stored relative path for a gallery image (spec path or on-disk slot file)."""
    path = entry.get("path")
    if isinstance(path, str) and path.strip():
        rel = path.lstrip("/")
        if _gallery_file_exists(rel):
            return rel
        # COS-backed keys may not exist locally — trust stored path when well-formed

        if is_showcase_logical_key(rel) and f"/{post_id}/" in f"/{rel}/":
            return rel

    for ext in GALLERY_IMAGE_SUFFIXES:
        for candidate in (
            f"showcase/posts/{post_id}/gallery_{slot}{ext}",
            f"case_square/{post_id}_gallery_{slot}{ext}",
        ):
            if _gallery_file_exists(candidate):
                return candidate

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
    """Count gallery image slots awaiting upload."""
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


def assert_post_ready_for_approval(
    *,
    case_type: str,
    spec: Optional[dict],
) -> None:
    """
    Reject approval when required media is still missing.

    COS create is metadata-first; gallery/attachment uploads complete later.
    Approving early makes the post immutable and can publish incomplete cases.
    """
    spec_obj = spec if isinstance(spec, dict) else {}
    if case_type == "teaching_design":
        attachment = spec_obj.get("attachment_path")
        if not isinstance(attachment, str) or not attachment.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Teaching design attachment is required before approval",
            )
    if isinstance(spec_obj.get("gallery"), list):
        assert_gallery_uploads_resolved(spec_obj)


def post_media_ready_for_approval(*, case_type: str, spec: Optional[dict]) -> bool:
    """True when approve would pass media completeness checks."""
    try:
        assert_post_ready_for_approval(case_type=case_type, spec=spec)
    except HTTPException:
        return False
    return True


def gallery_uploads_from_binding(bound: list[UploadFile]) -> list[UploadFile]:
    """Return non-empty gallery file parts from FastAPI File() binding."""
    return [upload for upload in bound if getattr(upload, "filename", None)]


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
            images.append(cast(UploadFile, upload))
    if images:
        return images
    for key, value in form.multi_items():
        if key != "gallery_images":
            continue
        upload = _form_upload_file(value)
        if upload is not None:
            images.append(cast(UploadFile, upload))
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
                "[Showcase] Missing gallery upload for post=%s slot=%s (need %s more)",
                post_id,
                slot,
                count_pending_gallery_images(spec_obj),
            )
            break
        upload = gallery_images[upload_idx]
        upload_idx += 1
        if not upload.filename:
            logger.warning("[Showcase] Gallery upload missing filename post=%s slot=%s", post_id, slot)
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


def _role_from_name_prefix(name_prefix: str) -> str:
    """Map legacy save_case_file prefixes to storage roles."""
    if name_prefix == "doc":
        return "attachment"
    return name_prefix


async def save_case_file(
    post_id: str,
    upload: UploadFile,
    allowed_suffixes: frozenset[str],
    name_prefix: str,
    max_bytes: int,
) -> str:
    """Validate and save an attachment or video via Showcase storage layer."""

    content = await upload.read()
    suffix = _suffix_or_raise(upload.filename, allowed_suffixes)
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Max {max_bytes // 1024 // 1024}MB",
        )
    _validate_magic_bytes(content, suffix)
    role = _role_from_name_prefix(name_prefix)
    logical_key = build_object_key(post_id, role, suffix)
    await put_bytes(logical_key, content)
    return logical_key


def save_spec_json(_post_id: str, _spec_obj: dict) -> None:
    """No-op: diagram spec lives in Postgres JSONB (no dual-write to disk)."""
    return


def delete_thumbnail(post_id: str) -> None:
    """Remove stored thumbnail for a post (best-effort; prefer delete_post_assets)."""

    try:
        delete_key_sync(build_object_key(post_id, "thumbnail", ".png"))
    except ValueError:
        pass
    legacy = SHOWCASE_DIR / f"{post_id}.png"
    if legacy.exists():
        try:
            legacy.unlink()
        except OSError as err:
            logger.warning("[Showcase] Failed to delete legacy thumbnail %s: %s", legacy, err)


def delete_spec_json(post_id: str) -> None:
    """Remove legacy on-disk spec JSON if present (spec is PG-backed now)."""
    path = SHOWCASE_DIR / f"{post_id}.json"
    if path.exists():
        try:
            path.unlink()
        except OSError as err:
            logger.warning("[Showcase] Failed to delete spec JSON %s: %s", path, err)


def delete_case_file(rel_path: str) -> None:
    """Delete a stored case attachment/video (best-effort)."""

    normalized = rel_path.lstrip("/").replace("\\", "/")
    if not is_showcase_logical_key(normalized):
        logger.warning("[Showcase] Refusing to delete path outside showcase: %s", rel_path)
        return
    delete_key_sync(normalized)


def prepare_post_id_and_spec(spec: str) -> tuple[str, dict]:
    """Parse diagram spec JSON and assign a new post UUID."""
    if len(spec.encode("utf-8")) > SPEC_MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Diagram spec too large",
        )
    return str(uuid.uuid4()), parse_spec_json(spec)


def parse_tags_json(tags: str) -> list[str]:
    """Parse tags form field into a deduplicated list of strings."""
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
