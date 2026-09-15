"""Admin API for MindMate teaching-design Word templates."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from routers.auth.dependencies import (
    require_organizations_read,
    require_settings_teaching_design,
    require_tab_settings_edit,
)
from services.mindmate.teaching_design_template_preview import ensure_template_preview_pdf
from services.mindmate.teaching_design_template_store import (
    delete_named_template,
    describe_template_catalog,
    list_template_options,
    resolve_download_path,
    restore_bundled_template,
    save_uploaded_template,
    update_named_template,
)
from services.utils.error_types import FILE_IO_ERRORS
from utils.auth.admin_scope import AdminScope

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/admin/teaching-design-template",
    tags=["admin-teaching-design-template"],
)

_DOCX_MEDIA = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


class TeachingDesignTemplatePatch(BaseModel):
    """Rename a template and/or pin it as the system default."""

    name: str | None = Field(default=None, max_length=80)
    is_default: bool | None = None


def _user_id(scope: AdminScope) -> int | None:
    raw_id = getattr(scope.actor, "id", None)
    if raw_id is None:
        return None
    return int(raw_id)


def _user_name(scope: AdminScope) -> str | None:
    name = getattr(scope.actor, "name", None)
    if isinstance(name, str) and name.strip():
        return name.strip()
    return None


def _catalog_or_500() -> dict:
    try:
        return describe_template_catalog()
    except FILE_IO_ERRORS as exc:
        logger.exception("[TeachingDesignTemplate] catalog_failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="teaching_design_template_missing",
        ) from exc


def _http_for_value_error(exc: ValueError) -> HTTPException:
    detail = str(exc) or "teaching_design_template_invalid"
    if detail == "teaching_design_template_too_large":
        code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    elif detail == "teaching_design_template_not_found":
        code = status.HTTP_404_NOT_FOUND
    else:
        code = status.HTTP_400_BAD_REQUEST
    return HTTPException(status_code=code, detail=detail)


@router.get("/options")
async def list_teaching_design_template_options(
    _scope: AdminScope = Depends(require_organizations_read),
) -> dict:
    """Template keys the 编辑学校 modal can assign."""
    return {"options": list_template_options()}


@router.get("")
async def get_teaching_design_template_catalog(
    _scope: AdminScope = Depends(require_settings_teaching_design),
) -> dict:
    """Named templates shown on the 系统设置 landing table."""
    return _catalog_or_500()


@router.get("/download")
async def download_default_teaching_design_template(
    _scope: AdminScope = Depends(require_settings_teaching_design),
) -> FileResponse:
    """Download the template that 跟随系统 currently uses."""
    default_id = str(_catalog_or_500().get("default_id") or "bundled")
    return _download_response(default_id)


@router.get("/{template_id}/download")
async def download_teaching_design_template(
    template_id: str,
    _scope: AdminScope = Depends(require_settings_teaching_design),
) -> FileResponse:
    """Download one catalog row."""
    return _download_response(template_id)


@router.get("/{template_id}/preview")
async def preview_teaching_design_template(
    template_id: str,
    _scope: AdminScope = Depends(require_settings_teaching_design),
) -> FileResponse:
    """LibreOffice PDF of the Word template, same reader as Showcase."""
    try:
        path = ensure_template_preview_pdf(template_id)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="teaching_design_template_missing",
        ) from exc
    except ValueError as exc:
        logger.warning("[TeachingDesignTemplate] preview_failed id=%s", template_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="teaching_design_template_preview_failed",
        ) from exc
    except FILE_IO_ERRORS as exc:
        logger.exception("[TeachingDesignTemplate] preview_io_failed id=%s", template_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="teaching_design_template_preview_failed",
        ) from exc
    if not path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="teaching_design_template_missing",
        )
    return FileResponse(
        path=str(path),
        media_type="application/pdf",
        filename=f"{Path(template_id).name}.pdf",
    )


@router.post("")
async def upload_teaching_design_template(
    file: UploadFile = File(...),
    name: str | None = Form(default=None),
    scope: AdminScope = Depends(require_tab_settings_edit),
    _view: AdminScope = Depends(require_settings_teaching_design),
) -> dict:
    """Add a Word template to the catalog."""
    payload = await file.read()
    original = file.filename or "teaching_design.docx"
    try:
        return save_uploaded_template(
            payload,
            original_filename=original,
            uploaded_by_user_id=_user_id(scope),
            uploaded_by_name=_user_name(scope),
            display_name=name,
        )
    except ValueError as exc:
        raise _http_for_value_error(exc) from exc
    except FILE_IO_ERRORS as exc:
        logger.exception("[TeachingDesignTemplate] upload_failed user=%s", _user_id(scope))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="teaching_design_template_write_failed",
        ) from exc


@router.patch("/{template_id}")
async def patch_teaching_design_template(
    template_id: str,
    body: TeachingDesignTemplatePatch,
    scope: AdminScope = Depends(require_tab_settings_edit),
    _view: AdminScope = Depends(require_settings_teaching_design),
) -> dict:
    """Edit the display name and/or system-default pin."""
    try:
        return update_named_template(
            template_id,
            name=body.name,
            is_default=body.is_default,
            uploaded_by_user_id=_user_id(scope),
            uploaded_by_name=_user_name(scope),
        )
    except ValueError as exc:
        raise _http_for_value_error(exc) from exc
    except FILE_IO_ERRORS as exc:
        logger.exception("[TeachingDesignTemplate] patch_failed id=%s", template_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="teaching_design_template_write_failed",
        ) from exc


@router.post("/{template_id}/file")
async def replace_teaching_design_template_file(
    template_id: str,
    file: UploadFile = File(...),
    scope: AdminScope = Depends(require_tab_settings_edit),
    _view: AdminScope = Depends(require_settings_teaching_design),
) -> dict:
    """Replace the Word file for an uploaded catalog row."""
    payload = await file.read()
    original = file.filename or "teaching_design.docx"
    try:
        return update_named_template(
            template_id,
            payload=payload,
            original_filename=original,
            uploaded_by_user_id=_user_id(scope),
            uploaded_by_name=_user_name(scope),
        )
    except ValueError as exc:
        raise _http_for_value_error(exc) from exc
    except FILE_IO_ERRORS as exc:
        logger.exception("[TeachingDesignTemplate] replace_failed id=%s", template_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="teaching_design_template_write_failed",
        ) from exc


@router.delete("/{template_id}")
async def delete_teaching_design_template(
    template_id: str,
    scope: AdminScope = Depends(require_tab_settings_edit),
    _view: AdminScope = Depends(require_settings_teaching_design),
) -> dict:
    """Remove an uploaded template from the catalog."""
    try:
        return delete_named_template(template_id)
    except ValueError as exc:
        raise _http_for_value_error(exc) from exc
    except FILE_IO_ERRORS as exc:
        logger.exception(
            "[TeachingDesignTemplate] delete_failed id=%s user=%s",
            template_id,
            _user_id(scope),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="teaching_design_template_write_failed",
        ) from exc


@router.post("/restore")
async def restore_teaching_design_template(
    scope: AdminScope = Depends(require_tab_settings_edit),
    _view: AdminScope = Depends(require_settings_teaching_design),
) -> dict:
    """Use the bundled form as the system default; keep uploaded rows."""
    try:
        return restore_bundled_template(user_id=_user_id(scope))
    except FILE_IO_ERRORS as exc:
        logger.exception("[TeachingDesignTemplate] restore_failed user=%s", _user_id(scope))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="teaching_design_template_restore_failed",
        ) from exc


def _download_response(template_id: str) -> FileResponse:
    try:
        path, filename = resolve_download_path(template_id)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="teaching_design_template_missing",
        ) from exc
    except FILE_IO_ERRORS as exc:
        logger.exception("[TeachingDesignTemplate] download_failed id=%s", template_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="teaching_design_template_missing",
        ) from exc
    if not path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="teaching_design_template_missing",
        )
    return FileResponse(path=str(path), media_type=_DOCX_MEDIA, filename=filename)
