"""Admin Database Management Router.

Endpoints for PostgreSQL stats, backup scan, PG dump export/import/merge,
and live-database orphan cleanup.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from config.database import engine
from routers.auth.dependencies import require_settings_database
from services.admin.database_export_service import (
    DUMP_EXT,
    DUMP_PREFIX,
    export_postgres_dump,
    get_pg_stats,
    import_postgres_dump,
    list_pg_dumps,
    scan_backup_folder,
)
from services.admin.pg_merge_service import (
    analyze_pg_dump,
    merge_pg_dump,
)
from services.admin.pg_orphan_service import (
    cleanup_pg_orphans,
    detect_pg_orphans,
)
from services.utils.error_types import BACKGROUND_INFRA_ERRORS, FILE_IO_ERRORS
from services.utils.pg_client_binaries import pg_tools_libpq_url
from utils.auth.admin_scope import AdminScope

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/auth/admin/database",
    tags=["Admin - Database Management"],
)

_backup_dir_env = os.getenv("BACKUP_DIR", "backup")
_project_root = Path(__file__).resolve().parents[2]
BACKUP_DIR = Path(_backup_dir_env) if Path(_backup_dir_env).is_absolute() else _project_root / _backup_dir_env


def _pg_tools_connection_uri() -> str:
    """Libpq URI for pg_dump/pg_restore — migrate role (BYPASSRLS), not runtime app role."""
    return pg_tools_libpq_url()


class FilenameBody(BaseModel):
    """Request body carrying a backup filename."""

    filename: str


@router.get("/stats")
async def database_stats(
    _scope: AdminScope = Depends(require_settings_database),
) -> Dict[str, Any]:
    """Current PostgreSQL table row counts and summary."""
    try:
        return await asyncio.to_thread(get_pg_stats, engine)
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.error("[AdminDB] stats failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.get("/scan")
async def scan_files(
    _scope: AdminScope = Depends(require_settings_database),
) -> Dict[str, Any]:
    """Scan backup/ folder for PG dump files."""
    return await asyncio.to_thread(scan_backup_folder, BACKUP_DIR)


@router.get("/dumps")
async def list_dumps(
    _scope: AdminScope = Depends(require_settings_database),
):
    """List available PostgreSQL dump files in backup/."""
    return await asyncio.to_thread(list_pg_dumps, BACKUP_DIR)


@router.get("/orphans")
async def detect_orphans(
    _scope: AdminScope = Depends(require_settings_database),
) -> Dict[str, int]:
    """Detect orphaned FK references in the current PostgreSQL database."""
    try:
        return await asyncio.to_thread(detect_pg_orphans, engine)
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.error("[AdminDB] orphan detect failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.post("/cleanup-orphans")
async def cleanup_orphans(
    _scope: AdminScope = Depends(require_settings_database),
) -> Dict[str, int]:
    """Clean up orphaned FK references in the PostgreSQL database."""
    try:
        return await asyncio.to_thread(cleanup_pg_orphans, engine)
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.error("[AdminDB] orphan cleanup failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.post("/export")
async def export_dump(
    _scope: AdminScope = Depends(require_settings_database),
) -> Dict[str, Any]:
    """Run pg_dump and save the file to backup/."""
    try:
        result = await asyncio.to_thread(
            export_postgres_dump,
            _pg_tools_connection_uri(),
            BACKUP_DIR,
        )
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Export failed"),
            )
        return result
    except FILE_IO_ERRORS as exc:
        logger.error("[AdminDB] export failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.post("/import-dump")
async def import_dump(
    body: FilenameBody,
    _scope: AdminScope = Depends(require_settings_database),
) -> Dict[str, Any]:
    """Restore a PG dump file from backup/ into the database. WARNING: replaces all data."""
    _validate_dump_filename(body.filename)

    dump_path = BACKUP_DIR / body.filename
    if not dump_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File not found: {body.filename}",
        )

    try:
        result = await asyncio.to_thread(
            import_postgres_dump,
            _pg_tools_connection_uri(),
            BACKUP_DIR,
            body.filename,
        )
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Import failed"),
            )
        return result
    except FILE_IO_ERRORS as exc:
        logger.error("[AdminDB] import failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.post("/analyze-dump")
async def analyze_dump_file(
    body: FilenameBody,
    _scope: AdminScope = Depends(require_settings_database),
) -> Dict[str, Any]:
    """Analyze a PG dump for merge preview (user/org matching, per-table counts)."""
    _validate_dump_filename(body.filename)

    dump_path = BACKUP_DIR / body.filename
    if not dump_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File not found: {body.filename}",
        )

    try:
        result = await asyncio.to_thread(analyze_pg_dump, dump_path)
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "Analysis failed"),
            )
        return result
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.error("[AdminDB] PG dump analysis failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.post("/merge-dump")
async def merge_dump_file(
    body: FilenameBody,
    _scope: AdminScope = Depends(require_settings_database),
) -> Dict[str, Any]:
    """Merge a PG dump into the live database (non-destructive, ID-remapped)."""
    _validate_dump_filename(body.filename)

    dump_path = BACKUP_DIR / body.filename
    if not dump_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File not found: {body.filename}",
        )

    try:
        result = await asyncio.to_thread(merge_pg_dump, dump_path)
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "Merge failed"),
            )
        return result
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.error("[AdminDB] PG dump merge failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


def _reject_path_traversal(filename: str) -> None:
    """Reject filenames containing path-traversal sequences."""
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename",
        )


def _validate_dump_filename(filename: str) -> None:
    """Reject path-traversal attempts and non-export dump names."""
    _reject_path_traversal(filename)
    if not filename.startswith(f"{DUMP_PREFIX}.") or not filename.endswith(DUMP_EXT):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only {DUMP_PREFIX}.*{DUMP_EXT} exports from this app can be used",
        )
