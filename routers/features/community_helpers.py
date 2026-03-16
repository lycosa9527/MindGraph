"""Community helpers: thumbnail, spec, and post creation/update logic."""

import json
import logging
import uuid
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from models.domain.community import CommunityPost

logger = logging.getLogger(__name__)

COMMUNITY_THUMBNAIL_DIR = Path("static/community")
COMMUNITY_THUMBNAIL_DIR.mkdir(parents=True, exist_ok=True)
THUMBNAIL_MAX_BYTES = 2 * 1024 * 1024  # 2MB
PNG_MAGIC = b'\x89PNG\r\n\x1a\n'
SPEC_MAX_BYTES = 500 * 1024  # 500KB


def _validate_thumbnail(content: bytes, _filename: Optional[str]) -> None:
    """Validate thumbnail: PNG magic bytes, size."""
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


def save_thumbnail(post_id: str, content: bytes) -> str:
    """Save thumbnail to disk, return relative path."""
    path = COMMUNITY_THUMBNAIL_DIR / f"{post_id}.png"
    path.write_bytes(content)
    return f"community/{post_id}.png"


async def save_thumbnail_from_upload(post_id: str, thumbnail: UploadFile) -> str:
    """Read, validate, and save thumbnail from upload. Returns relative path."""
    content = await thumbnail.read()
    _validate_thumbnail(content, thumbnail.filename)
    return save_thumbnail(post_id, content)


def save_spec_json(post_id: str, spec_obj: dict) -> None:
    """Save spec as JSON file alongside thumbnail for import/download."""
    path = COMMUNITY_THUMBNAIL_DIR / f"{post_id}.json"
    try:
        path.write_text(json.dumps(spec_obj, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as err:
        logger.warning("[Community] Failed to save spec JSON %s: %s", path, err)


def delete_thumbnail(post_id: str) -> None:
    """Delete thumbnail file if it exists."""
    path = COMMUNITY_THUMBNAIL_DIR / f"{post_id}.png"
    if path.exists():
        try:
            path.unlink()
        except OSError as err:
            logger.warning("[Community] Failed to delete thumbnail %s: %s", path, err)


def delete_spec_json(post_id: str) -> None:
    """Delete spec JSON file if it exists."""
    path = COMMUNITY_THUMBNAIL_DIR / f"{post_id}.json"
    if path.exists():
        try:
            path.unlink()
        except OSError as err:
            logger.warning("[Community] Failed to delete spec JSON %s: %s", path, err)


def parse_spec_json(spec: str) -> dict:
    """Parse spec JSON string, raise HTTPException on invalid JSON."""
    try:
        return json.loads(spec)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid spec JSON: {exc}",
        ) from exc


def prepare_post_id_and_spec(spec: str) -> tuple[str, dict]:
    """Generate post_id and parse spec. Validates spec size."""
    if len(spec.encode("utf-8")) > SPEC_MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Diagram spec too large",
        )
    return str(uuid.uuid4()), parse_spec_json(spec)


def validate_and_parse_spec(spec: str) -> dict:
    """Validate spec size and parse JSON. Raises HTTPException on error."""
    if len(spec.encode("utf-8")) > SPEC_MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Diagram spec too large",
        )
    return parse_spec_json(spec)


async def save_post_and_thumbnail(
    post_id: str,
    spec_obj: dict,
    thumbnail: UploadFile,
    title: str,
    description: str,
    category: Optional[str],
    diagram_type: str,
    author_id: int,
    db: Session,
) -> CommunityPost:
    """Save thumbnail, spec JSON, and create post record. Returns created post."""
    try:
        thumbnail_path = await save_thumbnail_from_upload(post_id, thumbnail)
    except OSError as err:
        logger.warning("[Community] Failed to save thumbnail for %s: %s", post_id, err)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save thumbnail",
        ) from err

    save_spec_json(post_id, spec_obj)

    post = CommunityPost(
        id=post_id,
        title=title.strip(),
        description=description.strip() or None,
        category=category,
        diagram_type=diagram_type,
        spec=json.dumps(spec_obj),
        thumbnail_path=thumbnail_path,
        author_id=author_id,
    )
    db.add(post)
    _commit_post_or_rollback(db, post, post_id)
    return post


def commit_and_refresh(db: Session, obj: object, error_detail: str) -> None:
    """Commit and refresh object. Raises HTTPException on failure."""
    try:
        db.commit()
        db.refresh(obj)
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_detail,
        ) from exc


def _commit_post_or_rollback(db: Session, post: CommunityPost, post_id: str) -> None:
    """Commit and refresh post, or rollback and clean up on failure."""
    try:
        db.commit()
        db.refresh(post)
    except Exception as exc:
        db.rollback()
        delete_thumbnail(post_id)
        delete_spec_json(post_id)
        logger.error("[Community] Failed to create post %s: %s", post_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create post",
        ) from exc


def commit_post_update(db: Session, post: CommunityPost) -> None:
    """Commit post update. Raises HTTPException on failure."""
    commit_and_refresh(db, post, "Failed to update post")


async def resolve_update_thumbnail_path(
    post: CommunityPost,
    post_id: str,
    thumbnail: Optional[UploadFile],
) -> str:
    """Return thumbnail path: use new upload if provided, else keep existing."""
    if thumbnail and thumbnail.filename:
        return await save_thumbnail_from_upload(post_id, thumbnail)
    return post.thumbnail_path or ""
