"""
MindMate export — Dify raw dump upload/import admin API.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field

from models.domain.auth import User
from models.domain.messages import Language, Messages
from routers.auth.dependencies import get_language_dependency, require_mindmate_export_access
from services.auth.security_logger import security_log
from services.dify.export.raw_dump_admin import (
    delete_incoming_file,
    delete_snapshot,
    import_incoming_file,
    import_pending,
    list_dump_inventory,
    save_uploaded_zip,
)
from utils.auth.request_helpers import get_client_ip

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/mindmate-export", tags=["admin", "mindmate-export"])


class ImportDumpsBody(BaseModel):
    """Import one named incoming zip or all pending zips."""

    filenames: Optional[List[str]] = Field(default=None, max_length=20)


@router.get("/dumps")
async def get_dump_inventory(
    _current_user: User = Depends(require_mindmate_export_access),
) -> dict:
    """List incoming zips, extracted snapshots, and active dump per server label."""
    return list_dump_inventory()


@router.post("/dumps/upload")
async def upload_dump_zip(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(require_mindmate_export_access),
    lang: Language = Depends(get_language_dependency),
) -> dict:
    """Upload a dify-dump_*.zip into incoming/ (web replacement for scp)."""
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.error("invalid_request", lang),
        )
    try:
        saved = await save_uploaded_zip(file.filename, file)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    security_log.data_export(
        "MindMate dump zip uploaded",
        user_id=int(current_user.id),
        ip=get_client_ip(request),
        filename=saved.path.name,
        bytes=saved.bytes_written,
        server_label=saved.server_label,
    )
    logger.info(
        "[MindMateExportDumps] upload user=%s file=%s bytes=%s label=%s",
        current_user.id,
        saved.path.name,
        saved.bytes_written,
        saved.server_label,
    )
    return {
        "name": saved.path.name,
        "bytes": saved.bytes_written,
        "server_label": saved.server_label,
        "inventory": list_dump_inventory(),
    }


@router.post("/dumps/import")
async def import_dump_zips(
    request: Request,
    body: Optional[ImportDumpsBody] = None,
    current_user: User = Depends(require_mindmate_export_access),
    _lang: Language = Depends(get_language_dependency),
) -> dict:
    """Extract incoming zips into data/dify-dumps/{dify|neodify}/."""
    if body is not None and body.filenames:
        imported: List[dict] = []
        errors: List[str] = []

        def _import_named() -> tuple[List[dict], List[str]]:
            rows: List[dict] = []
            errs: List[str] = []
            for name in body.filenames or []:
                try:
                    rows.append(import_incoming_file(name))
                except (OSError, ValueError, FileNotFoundError) as exc:
                    errs.append(f"{name}: {exc}")
            return rows, errs

        imported, errors = await asyncio.to_thread(_import_named)
        if errors and not imported:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="; ".join(errors),
            )
        result = {"imported": imported, "errors": errors}
    else:
        result = await asyncio.to_thread(import_pending)
    security_log.data_export(
        "MindMate dump import",
        user_id=int(current_user.id),
        ip=get_client_ip(request),
        imported_count=len(result.get("imported") or []),
        errors=result.get("errors"),
    )
    result["inventory"] = list_dump_inventory()
    return result


@router.delete("/dumps/incoming/{filename}")
async def remove_incoming_dump(
    filename: str,
    request: Request,
    current_user: User = Depends(require_mindmate_export_access),
    lang: Language = Depends(get_language_dependency),
) -> dict:
    """Delete an unimported zip from incoming/."""
    try:
        await asyncio.to_thread(delete_incoming_file, filename)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=Messages.error("not_found", lang),
        ) from exc
    security_log.data_export(
        "MindMate dump incoming deleted",
        user_id=int(current_user.id),
        ip=get_client_ip(request),
        filename=filename,
    )
    return {"ok": True, "inventory": list_dump_inventory()}


@router.delete("/dumps/snapshots/{label}/{timestamp}")
async def remove_dump_snapshot(
    label: str,
    timestamp: str,
    request: Request,
    current_user: User = Depends(require_mindmate_export_access),
    lang: Language = Depends(get_language_dependency),
) -> dict:
    """Delete one extracted snapshot directory."""
    try:
        await asyncio.to_thread(delete_snapshot, label, timestamp)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=Messages.error("not_found", lang),
        ) from exc
    security_log.data_export(
        "MindMate dump snapshot deleted",
        user_id=int(current_user.id),
        ip=get_client_ip(request),
        label=label,
        timestamp=timestamp,
    )
    return {"ok": True, "inventory": list_dump_inventory()}
