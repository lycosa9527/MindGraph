"""Training COS uploads and authenticated asset serve."""

from __future__ import annotations

import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse, RedirectResponse, Response
from pydantic import BaseModel, Field

from config.settings import config
from models.domain.auth import User
from services.features.training.courses.constants import ROLE_MAX_BYTES, ROLE_MIME
from services.features.training.courses.repository import add_asset, get_course
from services.features.training.permissions import can_lead_any_training, is_org_teacher_target
from services.features.training.session_store import get_session
from services.features.training.session_view import is_active_session
from services.features.training.storage.backend import (
    cos_training_enabled,
    create_presigned_get,
    create_presigned_put,
    get_bytes,
    head_object_async,
    put_bytes,
    storage_backend,
)
from services.features.training.storage.grants import pop_upload_grant, save_upload_grant
from services.features.training.roles.catalog import (
    ROLE_CONTENT_TYPE,
    is_packed_role_key,
    packed_role_file,
    parse_packed_role_key,
)
from services.features.training.roles.publish import (
    ensure_packed_roles_on_cos,
    packed_role_cos_prefixes,
)
from services.features.training.storage.keys import (
    ASSET_ROLES,
    build_object_key,
    course_id_from_key,
    is_scoped_course_object_key,
    resolve_local_safe,
    suffix_for_upload,
    training_public_asset_url,
)
from services.features.training.training_logger import log_training
from utils.auth import get_current_user
from utils.db.session_open import system_rls_session

logger = logging.getLogger(__name__)
router = APIRouter()
_ASSET_CACHE = {"Cache-Control": "private, max-age=120"}


class AssetInitBody(BaseModel):
    """Start a course-folder upload."""

    course_id: str = Field(min_length=36, max_length=36)
    role: str = Field(min_length=1, max_length=20)
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=1, max_length=128)
    size_bytes: int = Field(ge=1)


def _require_author(user: User) -> None:
    if not can_lead_any_training(user):
        raise HTTPException(status_code=403, detail="Training author access required")


@router.post("/assets/init")
async def init_training_asset(
    body: AssetInitBody,
    current_user: User = Depends(get_current_user),
):
    """Grant a key under this course's COS folder."""
    _require_author(current_user)
    if body.role not in ASSET_ROLES:
        raise HTTPException(status_code=400, detail="Invalid upload role")
    allowed = ROLE_MIME[body.role]
    if body.content_type.split(";")[0].strip().lower() not in allowed:
        raise HTTPException(status_code=400, detail="Content type is not allowed")
    if body.size_bytes > ROLE_MAX_BYTES[body.role]:
        raise HTTPException(status_code=400, detail="File is too large")
    try:
        suffix = suffix_for_upload(body.filename, body.content_type)
        asset_id = str(uuid.uuid4())
        logical_key = build_object_key(body.course_id, body.role, asset_id, suffix)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    async with system_rls_session() as db:
        course = await get_course(db, body.course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    await save_upload_grant(
        user_id=int(current_user.id),
        course_id=body.course_id,
        role=body.role,
        logical_key=logical_key,
        content_type=body.content_type,
        max_bytes=ROLE_MAX_BYTES[body.role],
    )
    put_url = None
    if config.COURSE_BUILDER_LOAD_FROM_COS:
        put_url = create_presigned_put(logical_key, body.content_type)
    backend = storage_backend()
    log_training(
        logger,
        "asset_init",
        prefix="[Training/COS]",
        actor_id=int(current_user.id),
        course_id=body.course_id,
        role=body.role,
        asset_id=asset_id,
        key=logical_key,
        bytes=body.size_bytes,
        backend=backend,
        presign=bool(put_url),
    )
    return {
        "key": logical_key,
        "asset_id": asset_id,
        "put_url": put_url,
        "backend": backend,
        "headers": {"Content-Type": body.content_type} if put_url else {},
    }


@router.post("/assets/complete")
async def complete_training_asset(
    course_id: str = Form(...),
    role: str = Form(...),
    key: str = Form(...),
    asset_id: str = Form(...),
    file: Optional[UploadFile] = File(default=None),
    current_user: User = Depends(get_current_user),
):
    """Verify the object and bind it to the course."""
    _require_author(current_user)
    grant = await pop_upload_grant(
        user_id=int(current_user.id),
        course_id=course_id,
        role=role,
    )
    if grant is None:
        log_training(
            logger,
            "asset_grant_missing",
            level=logging.WARNING,
            prefix="[Training/COS]",
            actor_id=int(current_user.id),
            course_id=course_id,
            role=role,
            key=key,
        )
        raise HTTPException(status_code=400, detail="Upload grant missing or expired")
    if grant.get("key") != key or grant.get("course_id") != course_id:
        raise HTTPException(status_code=400, detail="Upload grant does not match this course")
    if not is_scoped_course_object_key(key):
        raise HTTPException(status_code=400, detail="Invalid object key")
    if course_id_from_key(key) != course_id:
        raise HTTPException(status_code=400, detail="Key is not in this course folder")

    if file is not None:
        data = await file.read()
        if len(data) > int(grant.get("max_bytes") or 0):
            raise HTTPException(status_code=400, detail="File is too large")
        await put_bytes(
            key,
            data,
            content_type=str(grant.get("content_type") or "application/octet-stream"),
        )
        size = len(data)
    else:
        if not cos_training_enabled():
            raise HTTPException(status_code=400, detail="File body required when COS is off")
        meta = await head_object_async(key)
        if meta is None:
            raise HTTPException(status_code=400, detail="Object not found in course folder")
        size = int(meta.get("ContentLength") or 0)

    async with system_rls_session() as db:
        course = await get_course(db, course_id)
        if course is None:
            raise HTTPException(status_code=404, detail="Course not found")
        asset = await add_asset(
            db,
            course,
            asset_id=asset_id,
            role=role,
            logical_key=key,
            mime=str(grant.get("content_type") or "application/octet-stream"),
            bytes_size=size,
        )
        await db.commit()
    log_training(
        logger,
        "asset_complete",
        prefix="[Training/COS]",
        actor_id=int(current_user.id),
        course_id=course_id,
        role=role,
        asset_id=asset.id,
        key=key,
        bytes=size,
        source="multipart" if file is not None else "cos_head",
        backend=storage_backend(),
    )
    return {
        "id": asset.id,
        "role": asset.role,
        "url": training_public_asset_url(asset.logical_key),
        "logical_key": asset.logical_key,
    }


async def can_read_training_asset(user: User, course_id: str) -> bool:
    """Authors always; teachers only during a live or paused session for this course."""
    if can_lead_any_training(user):
        return True
    org_id = getattr(user, "organization_id", None)
    if org_id is None or not is_org_teacher_target(user, int(org_id)):
        return False
    session = await get_session(int(org_id))
    if session is None or not is_active_session(session):
        return False
    return str(session.get("course_id") or "") == course_id


async def can_read_packed_role(_user: User) -> bool:
    """Packed brand mascots: any signed-in user (Course Builder + 研习社)."""
    return True


def _repo_packed_role_response(parsed: tuple[str, bool]) -> Response:
    """Git-packed WebP when COURSE_BUILDER_LOAD_FROM_COS is off or COS misses."""
    role_id, thumb = parsed
    path = packed_role_file(role_id, thumb=thumb)
    if path is not None:
        return FileResponse(path, media_type=ROLE_CONTENT_TYPE, headers=_ASSET_CACHE)
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


async def _serve_packed_role(normalized: str, proxy: bool) -> Response:
    parsed = parse_packed_role_key(normalized)
    if parsed is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if not config.COURSE_BUILDER_LOAD_FROM_COS:
        return _repo_packed_role_response(parsed)
    prefixes = packed_role_cos_prefixes()
    if prefixes:
        await ensure_packed_roles_on_cos()
    if prefixes and cos_training_enabled() and not proxy:
        url = create_presigned_get(normalized)
        if url:
            return RedirectResponse(url, status_code=302, headers=_ASSET_CACHE)
    if prefixes and cos_training_enabled() and proxy:
        data = await get_bytes(normalized)
        if data is not None:
            return Response(
                content=data,
                media_type=ROLE_CONTENT_TYPE,
                headers=_ASSET_CACHE,
            )
    return _repo_packed_role_response(parsed)


@router.get("/assets/{asset_path:path}")
async def download_training_asset(
    asset_path: str,
    proxy: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
):
    """AuthZ then 302 presigned GET, or local/proxy bytes."""
    normalized = asset_path.lstrip("/").replace("\\", "/")
    if is_packed_role_key(normalized):
        if not await can_read_packed_role(current_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Training access required",
            )
        return await _serve_packed_role(normalized, proxy)
    if not is_scoped_course_object_key(normalized):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    course_id = course_id_from_key(normalized)
    if course_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if not await can_read_training_asset(current_user, course_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Training access required")

    serve_from_server = proxy or not cos_training_enabled() or not config.COURSE_BUILDER_LOAD_FROM_COS
    if not serve_from_server:
        url = create_presigned_get(normalized)
        if url:
            return RedirectResponse(url, status_code=302, headers=_ASSET_CACHE)
        raise HTTPException(status_code=404, detail="Not found")
    try:
        path = resolve_local_safe(normalized)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Not found") from exc
    if path.is_file():
        return FileResponse(path, headers=_ASSET_CACHE)
    data = await get_bytes(normalized)
    if data is None:
        raise HTTPException(status_code=404, detail="Not found")
    return Response(
        content=data,
        media_type="application/octet-stream",
        headers=_ASSET_CACHE,
    )
