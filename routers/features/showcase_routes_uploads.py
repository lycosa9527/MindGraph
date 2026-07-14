"""
Showcase media uploads: draft post → init → browser PUT → complete.

Industry contract:
- Short-TTL presigned PUT when COS on; local complete accepts file body when COS off
- Grants bind key to user+post+role (anti-swap)
- Complete verifies head_object + magic-byte sample

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_async_db
from config.settings import config
from models.domain.auth import User
from models.domain.showcase import ShowcasePost
from routers.api.helpers import check_endpoint_rate_limit, get_rate_limit_identifier
from routers.features.showcase_common import (
    _format_post,
    _load_post_for_format,
    _validate_post_id,
)
from routers.features.showcase_helpers import (
    _validate_magic_bytes,
    _validate_thumbnail,
    showcase_public_asset_url,
)
from routers.features.showcase_permissions import can_edit_case
from services.redis.cache import redis_showcase_cache as showcase_cache
from services.showcase.infra.observability import showcase_extra
from services.showcase.storage import (
    build_object_key,
    cos_showcase_enabled,
    create_presigned_put,
    delete_key,
    get_bytes,
    head_object_async,
    put_bytes,
    storage_backend,
)
from services.showcase.uploads.grants import pop_upload_grant, save_upload_grant
from services.showcase.uploads.pipeline import (
    apply_key_to_post,
    log_upload_complete,
    log_upload_complete_fail,
    log_upload_init,
    log_upload_init_fail,
)
from services.showcase.uploads.roles import (
    UploadRoleSpec,
    assert_content_type_allowed,
    resolve_upload_role,
    suffix_from_filename,
)
from services.utils.error_types import DATABASE_ERRORS
from utils.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()

MAGIC_SAMPLE_BYTES = 512


class UploadInitBody(BaseModel):
    """Request body for uploads/init."""

    role: str = Field(..., min_length=1, max_length=32)
    filename: str = Field(..., min_length=1, max_length=255)
    content_type: str = Field(..., min_length=1, max_length=128)
    size_bytes: int = Field(..., ge=1)


class UploadCompleteBody(BaseModel):
    """Request body for uploads/complete (COS path; local may use multipart instead)."""

    role: str = Field(..., min_length=1, max_length=32)
    key: str = Field(..., min_length=1, max_length=512)
    filename: Optional[str] = Field(None, max_length=255)


def reject_if_cos_multipart_files_present(files_present: bool) -> None:
    """When COS is on, large files must not transit FastAPI."""
    if cos_showcase_enabled() and files_present:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=("Direct multipart file uploads are disabled; use uploads/init then uploads/complete"),
        )


async def _load_editable_post(
    db: AsyncSession,
    post_id: str,
    current_user: User,
) -> ShowcasePost:
    post = (await db.execute(select(ShowcasePost).where(ShowcasePost.id == post_id))).scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    if not await can_edit_case(post, current_user, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot upload to this case",
        )
    return post


async def _apply_key_to_post(
    post: ShowcasePost,
    *,
    role_spec: UploadRoleSpec,
    logical_key: str,
    filename: Optional[str],
) -> Optional[str]:
    """Persist logical key onto post fields; returns previous key to delete."""
    return apply_key_to_post(
        post,
        role_spec=role_spec,
        logical_key=logical_key,
        filename=filename,
    )


def _validate_uploaded_bytes(role_spec: UploadRoleSpec, suffix: str, data: bytes) -> None:
    if role_spec.is_thumbnail:
        _validate_thumbnail(data)
        return
    _validate_magic_bytes(data, suffix)


@router.post("/posts/{post_id}/uploads/init")
async def init_showcase_upload(
    post_id: str,
    body: UploadInitBody,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Mint a short-lived upload grant (presigned PUT when COS enabled)."""
    _validate_post_id(post_id)
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit(
        "showcase_upload_init",
        identifier,
        max_requests=60,
        window_seconds=60,
    )

    await _load_editable_post(db, post_id, current_user)

    try:
        role_spec = resolve_upload_role(body.role)
        suffix = suffix_from_filename(body.filename, role_spec.allowed_suffixes)
        assert_content_type_allowed(suffix, body.content_type)
    except ValueError as exc:
        log_upload_init_fail(
            post_id=post_id,
            user_id=current_user.id,
            role=body.role,
            reason=str(exc),
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if body.size_bytes > role_spec.max_bytes:
        log_upload_init_fail(
            post_id=post_id,
            user_id=current_user.id,
            role=role_spec.role,
            reason="file_too_large",
        )
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Max {role_spec.max_bytes // 1024 // 1024}MB",
        )

    try:
        logical_key = build_object_key(post_id, role_spec.role, suffix)
    except ValueError as exc:
        log_upload_init_fail(
            post_id=post_id,
            user_id=current_user.id,
            role=role_spec.role,
            reason=str(exc),
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    ttl = config.COS_SHOWCASE_PRESIGN_PUT_TTL
    presign = create_presigned_put(logical_key, content_type=body.content_type)
    if not presign:
        log_upload_init_fail(
            post_id=post_id,
            user_id=current_user.id,
            role=role_spec.role,
            reason="presign_unavailable",
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Upload signing unavailable",
        )

    await save_upload_grant(
        user_id=current_user.id,
        post_id=post_id,
        role=role_spec.role,
        logical_key=logical_key,
        content_type=body.content_type,
        max_bytes=role_spec.max_bytes,
        ttl_seconds=ttl,
    )
    log_upload_init(
        post_id=post_id,
        user_id=current_user.id,
        role=role_spec.role,
        logical_key=logical_key,
        put_url_present=bool(presign.get("put_url")),
    )
    logger.info(
        "[Showcase] upload_init post=%s role=%s backend=%s",
        post_id,
        role_spec.role,
        storage_backend(),
        extra=showcase_extra(
            "upload_init",
            post_id=post_id,
            user_id=current_user.id,
            role=role_spec.role,
            key=logical_key,
            backend=storage_backend(),
        ),
    )

    return {
        "key": logical_key,
        "put_url": presign.get("put_url"),
        "storage": presign.get("storage"),
        "headers": presign.get("headers") or {"Content-Type": body.content_type},
        "expires_in": presign.get("expires_in", ttl),
        "role": role_spec.role,
        "max_bytes": role_spec.max_bytes,
    }


@router.post("/posts/{post_id}/uploads/complete")
async def complete_showcase_upload(
    post_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
    file: Optional[UploadFile] = File(None),
):
    """
    Finalize upload after browser PUT (COS) or accept file body (local fallback).

    JSON body: {role, key, filename?} — used when COS put_url was used.
    Multipart: role + key (+ file) — used when put_url is null (local).
    """
    _validate_post_id(post_id)
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit(
        "showcase_upload_complete",
        identifier,
        max_requests=60,
        window_seconds=60,
    )

    content_type_header = (request.headers.get("content-type") or "").lower()
    role = ""
    key = ""
    filename: Optional[str] = None
    local_bytes: Optional[bytes] = None

    if "multipart/form-data" in content_type_header:
        form = await request.form()
        role = str(form.get("role") or "")
        key = str(form.get("key") or "")
        raw_name = form.get("filename")
        if isinstance(raw_name, str) and raw_name:
            filename = raw_name
        upload = form.get("file")
        if isinstance(upload, UploadFile):
            local_bytes = await upload.read()
            if not filename and upload.filename:
                filename = Path(upload.filename).name
        elif file is not None and file.filename:
            local_bytes = await file.read()
            filename = filename or Path(file.filename).name
    else:
        try:
            payload = UploadCompleteBody.model_validate(await request.json())
        except (ValueError, TypeError) as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid complete payload",
            ) from exc
        role = payload.role
        key = payload.key
        filename = payload.filename

    if not role or not key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="role and key are required",
        )

    try:
        role_spec = resolve_upload_role(role)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    grant = await pop_upload_grant(
        user_id=current_user.id,
        post_id=post_id,
        role=role_spec.role,
    )
    if not grant or grant.get("key") != key:
        log_upload_complete_fail(
            post_id=post_id,
            user_id=current_user.id,
            role=role_spec.role,
            reason="grant_missing_or_mismatch",
            key=key,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Upload grant missing or key mismatch",
        )

    if not key.startswith(f"showcase/posts/{post_id}/"):
        log_upload_complete_fail(
            post_id=post_id,
            user_id=current_user.id,
            role=role_spec.role,
            reason="key_post_mismatch",
            key=key,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Key does not belong to this post",
        )

    max_bytes = int(grant.get("max_bytes") or role_spec.max_bytes)
    suffix = Path(key).suffix.lower()

    if local_bytes is not None:
        if cos_showcase_enabled():
            log_upload_complete_fail(
                post_id=post_id,
                user_id=current_user.id,
                role=role_spec.role,
                reason="local_body_with_cos",
                key=key,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Local file body not accepted when COS is enabled",
            )
        if len(local_bytes) > max_bytes:
            log_upload_complete_fail(
                post_id=post_id,
                user_id=current_user.id,
                role=role_spec.role,
                reason="file_too_large",
                key=key,
            )
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="File too large",
            )
        try:
            _validate_uploaded_bytes(role_spec, suffix, local_bytes)
        except HTTPException:
            log_upload_complete_fail(
                post_id=post_id,
                user_id=current_user.id,
                role=role_spec.role,
                reason="magic_bytes_rejected",
                key=key,
            )
            raise
        await put_bytes(key, local_bytes)
    else:
        meta = await head_object_async(key)
        if not meta:
            log_upload_complete_fail(
                post_id=post_id,
                user_id=current_user.id,
                role=role_spec.role,
                reason="object_not_found",
                key=key,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded object not found",
            )
        size_raw = meta.get("Content-Length") or meta.get("content-length") or "0"
        try:
            size = int(size_raw)
        except (TypeError, ValueError):
            size = 0
        if size <= 0 or size > max_bytes:
            await delete_key(key)
            log_upload_complete_fail(
                post_id=post_id,
                user_id=current_user.id,
                role=role_spec.role,
                reason="object_size_invalid",
                key=key,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded object size invalid",
            )
        sample = await get_bytes(key, max_bytes=MAGIC_SAMPLE_BYTES)
        if sample is None:
            log_upload_complete_fail(
                post_id=post_id,
                user_id=current_user.id,
                role=role_spec.role,
                reason="object_unreadable",
                key=key,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded object not readable",
            )
        try:
            if role_spec.is_thumbnail:
                if size > role_spec.max_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Thumbnail too large",
                    )
                if not sample.startswith(b"\x89PNG\r\n\x1a\n"):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid PNG file format",
                    )
            else:
                _validate_magic_bytes(sample, suffix)
        except HTTPException:
            await delete_key(key)
            log_upload_complete_fail(
                post_id=post_id,
                user_id=current_user.id,
                role=role_spec.role,
                reason="magic_bytes_rejected",
                key=key,
            )
            raise

    post = await _load_editable_post(db, post_id, current_user)
    previous = await _apply_key_to_post(
        post,
        role_spec=role_spec,
        logical_key=key,
        filename=filename,
    )
    try:
        await db.commit()
    except DATABASE_ERRORS as exc:
        await db.rollback()
        log_upload_complete_fail(
            post_id=post_id,
            user_id=current_user.id,
            role=role_spec.role,
            reason="db_commit_failed",
            key=key,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save upload",
        ) from exc

    if previous and previous != key:
        await delete_key(previous)

    await showcase_cache.invalidate_post(post_id)
    log_upload_complete(
        post_id=post_id,
        user_id=current_user.id,
        role=role_spec.role,
        logical_key=key,
    )
    post = await _load_post_for_format(db, post_id)
    return {
        "key": key,
        "url": showcase_public_asset_url(key),
        "post": await _format_post(post, current_user, db),
    }
