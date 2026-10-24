"""List, upload, and download seminar background files.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from models.domain.auth import User
from models.domain.messages import Language
from routers.api.helpers import check_endpoint_rate_limit, get_rate_limit_identifier
from routers.auth.dependencies import get_language_dependency
from services.features.mindmate_collab.background_file_preview import (
    resolve_background_preview_pdf,
)
from services.features.mindmate_collab.background_files import (
    delete_background_file,
    get_background_file,
    list_background_files,
    load_folder_session,
    rename_background_file,
    resolve_background_download,
    save_background_file,
    set_background_file_pinned,
)
from services.features.mindmate_collab.group_members import user_observes_seminar
from services.features.mindmate_collab.seminar_shelf import shelve_seminar_item
from services.features.mindmate_collab.ws_broadcast import broadcast_to_all
from services.utils.error_types import DATABASE_ERRORS
from utils.auth import get_current_user
from utils.auth.school_tier import TIER_FEATURE_ONLINE_COLLAB, assert_user_has_school_tier_feature
from utils.db.session_open import actor_rls_session

router = APIRouter()
logger = logging.getLogger(__name__)

_STATUS = {
    "room_not_found": status.HTTP_404_NOT_FOUND,
    "forbidden": status.HTTP_403_FORBIDDEN,
    "file_type": status.HTTP_400_BAD_REQUEST,
    "file_too_large": status.HTTP_400_BAD_REQUEST,
    "file_limit": status.HTTP_400_BAD_REQUEST,
    "upload_failed": status.HTTP_503_SERVICE_UNAVAILABLE,
    "preview_unsupported": status.HTTP_400_BAD_REQUEST,
    "preview_missing": status.HTTP_404_NOT_FOUND,
    "preview_failed": status.HTTP_503_SERVICE_UNAVAILABLE,
}


async def _require_collab_tier(current_user: User, lang: Language) -> None:
    async with actor_rls_session(current_user) as db:
        await assert_user_has_school_tier_feature(
            db,
            current_user,
            TIER_FEATURE_ONLINE_COLLAB,
            lang,
        )


class BackgroundFileRenameBody(BaseModel):
    """Rename payload for one shared seminar file."""

    session_id: str = Field(..., min_length=8, max_length=36)
    filename: str = Field(..., min_length=1, max_length=180)


class BackgroundFilePinBody(BaseModel):
    """Pin / unpin payload for one shared seminar file."""

    session_id: str = Field(..., min_length=8, max_length=36)
    pinned: bool


class SeminarShelfBody(BaseModel):
    """Move a chat file or shared diagram onto 资源 or 产物."""

    kind: str = Field(..., pattern="^(file|diagram)$")
    destination: str = Field(..., pattern="^(resource|artifact)$")
    file_id: str = ""
    diagram_id: str = ""
    title: str = ""


def _content_disposition(kind: str, filename: str) -> str:
    """Attachment header that keeps non-ASCII seminar filenames."""
    fallback = filename.encode("ascii", "ignore").decode().replace('"', "") or "download"
    encoded = quote(filename)
    return f"{kind}; filename=\"{fallback}\"; filename*=UTF-8''{encoded}"


def _form_listed(raw: str) -> bool:
    """Multipart booleans arrive as text. Only an explicit false hides the file."""
    return raw.strip().lower() not in {"0", "false", "no", "off"}


async def _reject_observer(session_id: str, user_id: int) -> None:
    """观摩学习 may open files, not change or download them."""
    if await user_observes_seminar(session_id, user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="observer_readonly")


def _http_error(exc: ValueError) -> HTTPException:
    code = str(exc)
    return HTTPException(status_code=_STATUS.get(code, status.HTTP_400_BAD_REQUEST), detail=code)


@router.post("/{session_id}/shelf")
async def shelve_seminar_background_item(
    session_id: str,
    body: SeminarShelfBody,
    request: Request,
    current_user: User = Depends(get_current_user),
    lang: Language = Depends(get_language_dependency),
):
    """Archive one chat file or shared diagram into resources or artifacts."""
    await _require_collab_tier(current_user, lang)
    await check_endpoint_rate_limit(
        "mindmate_collab_seminar_shelf",
        get_rate_limit_identifier(current_user, request),
        max_requests=30,
        window_seconds=60,
    )
    try:
        session = await load_folder_session(current_user, session_id)
        await _reject_observer(session.id, int(current_user.id))
        return await shelve_seminar_item(
            session,
            current_user,
            kind=body.kind,
            destination=body.destination,
            file_id=body.file_id,
            diagram_id=body.diagram_id,
            title=body.title,
        )
    except ValueError as exc:
        raise _http_error(exc) from exc


@router.get("/background-files")
async def list_seminar_background_files(
    request: Request,
    session_id: str = Query(..., min_length=8, max_length=36),
    current_user: User = Depends(get_current_user),
    lang: Language = Depends(get_language_dependency),
):
    """List background files shared in this seminar."""
    await _require_collab_tier(current_user, lang)
    await check_endpoint_rate_limit(
        "mindmate_collab_background_files",
        get_rate_limit_identifier(current_user, request),
        max_requests=60,
        window_seconds=60,
    )
    try:
        session = await load_folder_session(current_user, session_id)
    except ValueError as exc:
        raise _http_error(exc) from exc
    return {"items": await list_background_files(session.id)}


@router.post("/background-files", status_code=status.HTTP_201_CREATED)
async def upload_seminar_background_file(
    request: Request,
    session_id: str = Form(...),
    file: UploadFile = File(...),
    listed: str = Form("true"),
    current_user: User = Depends(get_current_user),
    lang: Language = Depends(get_language_dependency),
):
    """Upload one background file that everyone in the seminar can open."""
    logger.info(
        "[SeminarFiles] upload start user=%s session=%s filename=%s",
        current_user.id,
        session_id,
        getattr(file, "filename", None),
    )
    await _require_collab_tier(current_user, lang)
    await check_endpoint_rate_limit(
        "mindmate_collab_background_upload",
        get_rate_limit_identifier(current_user, request),
        max_requests=20,
        window_seconds=60,
    )
    try:
        session = await load_folder_session(current_user, session_id)
        await _reject_observer(session.id, int(current_user.id))
        saved = await save_background_file(
            session,
            current_user,
            file,
            listed=_form_listed(listed),
        )
        logger.info(
            "[SeminarFiles] upload ok user=%s session=%s file_id=%s",
            current_user.id,
            session.id,
            saved.get("id"),
        )
        return saved
    except ValueError as exc:
        logger.warning(
            "[SeminarFiles] upload rejected user=%s session=%s detail=%s",
            current_user.id,
            session_id,
            exc,
        )
        raise _http_error(exc) from exc
    except DATABASE_ERRORS:
        logger.exception(
            "[SeminarFiles] upload failed user=%s session=%s filename=%s",
            current_user.id,
            session_id,
            getattr(file, "filename", None),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="upload_failed",
        ) from None


@router.patch("/background-files/{file_id}")
async def rename_seminar_background_file(
    file_id: str,
    body: BackgroundFileRenameBody,
    request: Request,
    current_user: User = Depends(get_current_user),
    lang: Language = Depends(get_language_dependency),
):
    """Rename one shared background file."""
    await _require_collab_tier(current_user, lang)
    await check_endpoint_rate_limit(
        "mindmate_collab_background_rename",
        get_rate_limit_identifier(current_user, request),
        max_requests=30,
        window_seconds=60,
    )
    try:
        session = await load_folder_session(current_user, body.session_id)
        await _reject_observer(session.id, int(current_user.id))
        return await rename_background_file(session.id, file_id, body.filename)
    except ValueError as exc:
        raise _http_error(exc) from exc


@router.post("/background-files/{file_id}/pin")
async def pin_seminar_background_file(
    file_id: str,
    body: BackgroundFilePinBody,
    request: Request,
    current_user: User = Depends(get_current_user),
    lang: Language = Depends(get_language_dependency),
):
    """Pin or unpin one shared background file."""
    await _require_collab_tier(current_user, lang)
    await check_endpoint_rate_limit(
        "mindmate_collab_background_pin",
        get_rate_limit_identifier(current_user, request),
        max_requests=40,
        window_seconds=60,
    )
    try:
        session = await load_folder_session(current_user, body.session_id)
        await _reject_observer(session.id, int(current_user.id))
        return await set_background_file_pinned(session.id, file_id, body.pinned)
    except ValueError as exc:
        raise _http_error(exc) from exc


@router.delete("/background-files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_seminar_background_file(
    file_id: str,
    request: Request,
    session_id: str = Query(..., min_length=8, max_length=36),
    current_user: User = Depends(get_current_user),
    lang: Language = Depends(get_language_dependency),
):
    """Delete one shared background file."""
    await _require_collab_tier(current_user, lang)
    await check_endpoint_rate_limit(
        "mindmate_collab_background_delete",
        get_rate_limit_identifier(current_user, request),
        max_requests=30,
        window_seconds=60,
    )
    try:
        session = await load_folder_session(current_user, session_id)
        await _reject_observer(session.id, int(current_user.id))
        removed = await delete_background_file(session.id, file_id)
        if removed:
            actor_name = (current_user.name or "").strip()
            await broadcast_to_all(
                session.code,
                {
                    "type": "seminar_shelf",
                    "destination": "removed",
                    "shelf": removed.get("shelf") or "artifact",
                    "file": removed,
                    "actor_user_id": int(current_user.id),
                    "actor_name": actor_name,
                },
            )
    except ValueError as exc:
        raise _http_error(exc) from exc


@router.get("/background-files/{file_id}")
async def get_seminar_background_file(
    file_id: str,
    request: Request,
    session_id: str = Query(..., min_length=8, max_length=36),
    current_user: User = Depends(get_current_user),
    lang: Language = Depends(get_language_dependency),
):
    """Return metadata for one seminar file, including unlisted chat attachments."""
    await _require_collab_tier(current_user, lang)
    await check_endpoint_rate_limit(
        "mindmate_collab_background_file",
        get_rate_limit_identifier(current_user, request),
        max_requests=120,
        window_seconds=60,
    )
    try:
        session = await load_folder_session(current_user, session_id)
    except ValueError as exc:
        raise _http_error(exc) from exc
    payload = await get_background_file(session.id, file_id)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="room_not_found")
    return payload


@router.get("/background-files/{file_id}/download")
async def download_seminar_background_file(
    file_id: str,
    request: Request,
    session_id: str = Query(..., min_length=8, max_length=36),
    current_user: User = Depends(get_current_user),
    lang: Language = Depends(get_language_dependency),
):
    """Download one shared background file."""
    await _require_collab_tier(current_user, lang)
    await check_endpoint_rate_limit(
        "mindmate_collab_background_download",
        get_rate_limit_identifier(current_user, request),
        max_requests=60,
        window_seconds=60,
    )
    try:
        session = await load_folder_session(current_user, session_id)
        await _reject_observer(session.id, int(current_user.id))
    except ValueError as exc:
        raise _http_error(exc) from exc
    resolved = await resolve_background_download(session.id, file_id)
    if resolved is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="room_not_found")
    inline = resolved.content_type.startswith(("image/", "audio/"))
    disposition = "inline" if inline else "attachment"
    if resolved.disk_path is not None:
        return FileResponse(
            path=str(resolved.disk_path),
            media_type=resolved.content_type,
            filename=resolved.filename,
            content_disposition_type=disposition,
        )
    if resolved.body is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="room_not_found")
    return Response(
        content=resolved.body,
        media_type=resolved.content_type,
        headers={"Content-Disposition": _content_disposition(disposition, resolved.filename)},
    )


@router.get("/background-files/{file_id}/preview")
async def preview_seminar_background_file(
    file_id: str,
    request: Request,
    session_id: str = Query(..., min_length=8, max_length=36),
    current_user: User = Depends(get_current_user),
    lang: Language = Depends(get_language_dependency),
):
    """Inline-readable PDF for a shared file (native PDF or LibreOffice convert)."""
    await _require_collab_tier(current_user, lang)
    await check_endpoint_rate_limit(
        "mindmate_collab_background_preview",
        get_rate_limit_identifier(current_user, request),
        max_requests=30,
        window_seconds=60,
    )
    try:
        session = await load_folder_session(current_user, session_id)
        pdf_path, download_name = await resolve_background_preview_pdf(session.id, file_id)
    except ValueError as exc:
        detail = str(exc)
        if detail.startswith("LibreOffice") or "LibreOffice" in detail:
            logger.warning(
                "[SeminarFiles] preview convert failed user=%s file=%s detail=%s",
                current_user.id,
                file_id,
                detail[:200],
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="preview_failed",
            ) from exc
        logger.warning(
            "[SeminarFiles] preview rejected user=%s file=%s detail=%s",
            current_user.id,
            file_id,
            detail,
        )
        raise _http_error(exc) from exc
    except DATABASE_ERRORS:
        logger.exception(
            "[SeminarFiles] preview failed user=%s session=%s file=%s",
            current_user.id,
            session_id,
            file_id,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="preview_failed",
        ) from None
    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename=download_name,
        content_disposition_type="inline",
    )
