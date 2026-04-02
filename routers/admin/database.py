"""Admin Database Management Router.

Endpoints for:
- Current PostgreSQL statistics
- Scanning the backup/ folder for SQLite and PG dump files
- Analyzing a SQLite file against the running PG database
- Merging SQLite data into PostgreSQL (with ID remapping)
- Cleaning up orphaned records in PostgreSQL
- Exporting / importing PostgreSQL dumps (all in backup/)
- Analyzing / merging PG dumps non-destructively (PG-to-PG merge)

Security: all endpoints require admin role.

Copyright 2024-2025 Beijing Siyuan Zhijiao Technology Co., Ltd.
All Rights Reserved -- Proprietary License
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from config.database import engine
from models.domain.auth import User
from routers.auth.dependencies import require_admin
from services.admin.database_export_service import (
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
from services.admin.sqlite_merge_service import (
    analyze_sqlite,
    merge_sqlite_into_postgres,
)
from services.admin.sqlite_orphan_service import (
    cleanup_pg_orphans,
    cleanup_sqlite_orphans,
    detect_pg_orphans,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/auth/admin/database",
    tags=["Admin - Database Management"],
)

_backup_dir_env = os.getenv("BACKUP_DIR", "backup")
_project_root = Path(__file__).resolve().parents[2]
BACKUP_DIR = Path(_backup_dir_env) if Path(_backup_dir_env).is_absolute() else _project_root / _backup_dir_env

_RAW_DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://mindgraph_user:mindgraph_password@localhost:5432/mindgraph",
)


def _raw_pg_url() -> str:
    """Return the raw PG URL (without SQLAlchemy driver prefix) for CLI tools."""
    url = _RAW_DB_URL
    for prefix in ("postgresql+psycopg://", "postgresql+psycopg2://"):
        if url.startswith(prefix):
            return "postgresql://" + url[len(prefix) :]
    return url


# ── request bodies ────────────────────────────────────────────────────


class FilenameBody(BaseModel):
    """Request body carrying a backup filename."""

    filename: str


# ── endpoints ─────────────────────────────────────────────────────────


@router.get("/stats")
async def database_stats(
    _admin: User = Depends(require_admin),
) -> Dict[str, Any]:
    """Current PostgreSQL table row counts and summary."""
    try:
        return get_pg_stats(engine)
    except Exception as exc:
        logger.error("[AdminDB] stats failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.get("/scan")
async def scan_files(
    _admin: User = Depends(require_admin),
) -> Dict[str, Any]:
    """Scan backup/ folder for SQLite and PG dump files."""
    return scan_backup_folder(BACKUP_DIR)


@router.get("/dumps")
async def list_dumps(
    _admin: User = Depends(require_admin),
):
    """List available PostgreSQL dump files in backup/."""
    return list_pg_dumps(BACKUP_DIR)


@router.post("/analyze")
def analyze_sqlite_file(
    body: FilenameBody,
    _admin: User = Depends(require_admin),
) -> Dict[str, Any]:
    """Analyze a SQLite file vs the running PostgreSQL database."""
    _validate_sqlite_filename(body.filename)

    sqlite_path = BACKUP_DIR / body.filename
    if not sqlite_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File not found: {body.filename}",
        )

    try:
        return analyze_sqlite(sqlite_path, engine)
    except Exception as exc:
        logger.error("[AdminDB] analyze failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.post("/cleanup-sqlite-orphans")
def cleanup_sqlite_orphans_endpoint(
    body: FilenameBody,
    _admin: User = Depends(require_admin),
) -> Dict[str, Any]:
    """Delete orphaned records from a SQLite file before merging."""
    _validate_sqlite_filename(body.filename)

    sqlite_path = BACKUP_DIR / body.filename
    if not sqlite_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File not found: {body.filename}",
        )

    try:
        return cleanup_sqlite_orphans(sqlite_path)
    except Exception as exc:
        logger.error(
            "[AdminDB] SQLite orphan cleanup failed: %s",
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.post("/merge")
def merge_sqlite(
    body: FilenameBody,
    _admin: User = Depends(require_admin),
) -> Dict[str, Any]:
    """Merge a SQLite file into the running PostgreSQL database."""
    _validate_sqlite_filename(body.filename)

    sqlite_path = BACKUP_DIR / body.filename
    if not sqlite_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File not found: {body.filename}",
        )

    try:
        return merge_sqlite_into_postgres(sqlite_path, engine)
    except Exception as exc:
        logger.error("[AdminDB] merge failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.get("/orphans")
def detect_orphans(
    _admin: User = Depends(require_admin),
) -> Dict[str, int]:
    """Detect orphaned FK references in the current PostgreSQL database."""
    try:
        return detect_pg_orphans(engine)
    except Exception as exc:
        logger.error("[AdminDB] orphan detect failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.post("/cleanup-orphans")
def cleanup_orphans(
    _admin: User = Depends(require_admin),
) -> Dict[str, int]:
    """Clean up orphaned FK references in the PostgreSQL database."""
    try:
        return cleanup_pg_orphans(engine)
    except Exception as exc:
        logger.error("[AdminDB] orphan cleanup failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.post("/export")
def export_dump(
    _admin: User = Depends(require_admin),
) -> Dict[str, Any]:
    """Run pg_dump and save the file to backup/."""
    try:
        result = export_postgres_dump(_raw_pg_url(), BACKUP_DIR, pg_engine=engine)
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Export failed"),
            )
        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("[AdminDB] export failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.post("/import-dump")
def import_dump(
    body: FilenameBody,
    _admin: User = Depends(require_admin),
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
        result = import_postgres_dump(
            _raw_pg_url(),
            BACKUP_DIR,
            body.filename,
            pg_engine=engine,
        )
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Import failed"),
            )
        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("[AdminDB] import failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.post("/analyze-dump")
def analyze_dump_file(
    body: FilenameBody,
    _admin: User = Depends(require_admin),
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
        result = analyze_pg_dump(dump_path, live_engine=engine)
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Analysis failed"),
            )
        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("[AdminDB] PG dump analysis failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.post("/merge-dump")
def merge_dump_file(
    body: FilenameBody,
    _admin: User = Depends(require_admin),
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
        result = merge_pg_dump(dump_path, live_engine=engine)
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Merge failed"),
            )
        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("[AdminDB] PG dump merge failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


# ── helpers ───────────────────────────────────────────────────────────


def _reject_path_traversal(filename: str) -> None:
    """Reject filenames containing path-traversal sequences."""
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename",
        )


def _validate_sqlite_filename(filename: str) -> None:
    """Reject path-traversal attempts and non-SQLite file names."""
    _reject_path_traversal(filename)
    if ".db" not in filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Not a SQLite database file",
        )


def _validate_dump_filename(filename: str) -> None:
    """Reject path-traversal attempts and non-dump file names."""
    _reject_path_traversal(filename)
    if not filename.endswith(".dump"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .dump files can be imported",
        )
