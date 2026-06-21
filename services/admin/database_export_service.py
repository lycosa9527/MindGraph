"""
PostgreSQL Dump / Restore Service (web-triggered)

Wraps pg_dump and pg_restore for the admin Database tab.
All dump files are saved to / read from the project ``backup/`` folder.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import json
import logging
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from config.database import init_db, libpq_database_url
from services.utils.error_types import DATABASE_ERRORS
from services.utils.pg_backup_manifest import (
    build_pg_dump_manifest,
    prepare_pg_dump_rls,
    resolve_stats_engine,
)
from services.utils.pg_client_binaries import (
    build_pg_dump_cmd,
    find_pg_client_binary,
    log_pg_dump_failure,
    pg_tools_connection_username,
)
from services.utils.pg_restore_prep import wipe_public_schema_before_restore

logger = logging.getLogger(__name__)

DUMP_PREFIX = "mindgraph.postgresql"
DUMP_EXT = ".dump"

_find_pg_binary = find_pg_client_binary


# ── backup folder scanning ───────────────────────────────────────────


def scan_backup_folder(backup_dir: Path) -> Dict[str, List[Dict[str, Any]]]:
    """
    Scan the backup folder for PG dump (*.dump) files.

    Returns ``{"pg_dumps": [...]}``, each item a dict with ``name``, ``size_bytes``,
    ``modified_at``.
    """
    if not backup_dir.exists():
        return {"pg_dumps": []}

    pg_dumps: List[Dict[str, Any]] = []

    for entry in sorted(backup_dir.iterdir()):
        if not entry.is_file():
            continue
        stat = entry.stat()
        info: Dict[str, Any] = {
            "name": entry.name,
            "size_bytes": stat.st_size,
            "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        }

        if entry.name.endswith(DUMP_EXT) and entry.name.startswith(f"{DUMP_PREFIX}."):
            manifest_path = backup_dir / f"{entry.name}.manifest.json"
            if manifest_path.exists():
                try:
                    manifest = json.loads(manifest_path.read_text())
                    info["manifest"] = manifest
                except (json.JSONDecodeError, OSError):
                    pass
            pg_dumps.append(info)

    pg_dumps.sort(key=lambda f: f["modified_at"], reverse=True)
    return {"pg_dumps": pg_dumps}


# ── DB stats ─────────────────────────────────────────────────────────


def get_pg_stats(pg_engine: Engine) -> Dict[str, Any]:
    """Return table row counts and summary from the live PostgreSQL db."""
    pg_inspector = inspect(pg_engine)
    table_names = sorted(pg_inspector.get_table_names())
    counts: Dict[str, int] = {}

    with pg_engine.connect() as conn:
        for table in table_names:
            try:
                result = conn.execute(text(f'SELECT COUNT(*) FROM "{table}"'))
                counts[table] = result.scalar() or 0
            except DATABASE_ERRORS:
                counts[table] = -1

    total_columns = 0
    for table in table_names:
        try:
            total_columns += len(pg_inspector.get_columns(table))
        except DATABASE_ERRORS:
            pass

    return {
        "table_count": len(table_names),
        "column_count": total_columns,
        "total_rows": sum(v for v in counts.values() if v >= 0),
        "tables": counts,
    }


# ── export (pg_dump) ─────────────────────────────────────────────────


def export_postgres_dump(
    db_url: str,
    backup_dir: Path,
) -> Dict[str, Any]:
    """
    Run ``pg_dump`` and save the output to ``backup/``.

    Returns a dict with ``success``, ``filename``, ``size_bytes``,
    ``manifest`` on success, or ``error`` on failure.
    """
    pg_dump = _find_pg_binary("pg_dump")
    if not pg_dump:
        return {"success": False, "error": "pg_dump not found on server"}

    rls_ok, rls_msg = prepare_pg_dump_rls()
    if not rls_ok:
        return {"success": False, "error": f"RLS bootstrap failed: {rls_msg}"}

    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
    filename = f"{DUMP_PREFIX}.{timestamp}{DUMP_EXT}"
    dump_path = backup_dir / filename

    dump_user = pg_tools_connection_username(db_url)
    logger.info("[DBExport] Running pg_dump (connection user=%s)", dump_user)

    cmd = build_pg_dump_cmd(pg_dump, dump_path, db_url)
    result = subprocess.run(
        cmd,
        capture_output=True,
        timeout=3600,
        check=False,
        text=True,
    )

    if result.returncode != 0:
        log_pg_dump_failure(result.stderr or result.stdout or "")
        if dump_path.exists():
            dump_path.unlink()
        return {
            "success": False,
            "error": (result.stderr or "pg_dump failed")[:500],
        }

    if not dump_path.exists() or dump_path.stat().st_size == 0:
        return {"success": False, "error": "Dump file empty or missing"}

    stats_engine = resolve_stats_engine(bootstrap_rls=False)
    try:
        manifest = build_pg_dump_manifest(
            dump_path,
            stats_engine,
            dump_file=filename,
        )
    finally:
        stats_engine.dispose()

    manifest_path = backup_dir / f"{filename}.manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))

    logger.info(
        "[DBExport] Dump saved: %s (%d bytes)",
        filename,
        dump_path.stat().st_size,
    )
    return {
        "success": True,
        "filename": filename,
        "size_bytes": dump_path.stat().st_size,
        "manifest": manifest,
    }


# ── import (pg_restore) ──────────────────────────────────────────────


def import_postgres_dump(
    db_url: str,
    backup_dir: Path,
    filename: str,
    pg_engine: Optional[Engine] = None,
) -> Dict[str, Any]:
    """
    Restore a ``.dump`` file from ``backup/`` into the PostgreSQL database.

    After ``pg_restore``, runs Alembic migrations so schema matches the current
    app (older backups may omit columns added in later revisions).

    WARNING: This replaces all existing data.
    """
    pg_restore = _find_pg_binary("pg_restore")
    if not pg_restore:
        return {"success": False, "error": "pg_restore not found on server"}

    dump_path = backup_dir / filename
    if not dump_path.exists():
        return {"success": False, "error": f"File not found: {filename}"}

    rls_ok, rls_msg = prepare_pg_dump_rls()
    if not rls_ok:
        return {"success": False, "error": f"RLS bootstrap failed: {rls_msg}"}

    owns_stats_engine = pg_engine is None
    restore_engine = pg_engine
    if restore_engine is None:
        restore_engine = resolve_stats_engine(bootstrap_rls=False)

    try:
        if not wipe_public_schema_before_restore(db_url, restore_engine):
            return {
                "success": False,
                "error": "Failed to prepare database (drop public schema)",
            }

        cmd = [
            pg_restore,
            "--no-owner",
            "--single-transaction",
            "-d",
            libpq_database_url(db_url),
            str(dump_path),
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=3600,
            check=False,
            text=True,
        )

        if result.returncode != 0:
            stderr = (result.stderr or "")[:500]
            logger.error(
                "pg_restore failed (exit %d): %s",
                result.returncode,
                stderr,
            )
            return {"success": False, "error": stderr}

        try:
            logger.info("[DBImport] Applying Alembic migrations after restore (schema may predate current ORM)")
            _run_alembic_after_pg_restore()
        except DATABASE_ERRORS as exc:
            logger.error("[DBImport] Post-restore migration failed: %s", exc, exc_info=True)
            return {
                "success": False,
                "error": (
                    "pg_restore finished but upgrading schema to current revision failed. "
                    f"Database may be inconsistent. Details: {exc}"
                )[:2000],
            }

        try:
            _reset_all_sequences(restore_engine)
        except DATABASE_ERRORS as exc:
            logger.debug("[DBImport] Sequence reset failed: %s", exc)

        logger.info("[DBImport] Restored %s successfully", filename)
        return {"success": True, "filename": filename}
    finally:
        if owns_stats_engine:
            restore_engine.dispose()


# ── list dumps ────────────────────────────────────────────────────────


def list_pg_dumps(backup_dir: Path) -> List[Dict[str, Any]]:
    """Return metadata for every ``.dump`` file in the backup folder."""
    if not backup_dir.exists():
        return []

    dumps: List[Dict[str, Any]] = []
    for entry in backup_dir.glob(f"{DUMP_PREFIX}.*{DUMP_EXT}"):
        if not entry.is_file():
            continue
        stat = entry.stat()
        info: Dict[str, Any] = {
            "name": entry.name,
            "size_bytes": stat.st_size,
            "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        }
        manifest_path = backup_dir / f"{entry.name}.manifest.json"
        if manifest_path.exists():
            try:
                info["manifest"] = json.loads(manifest_path.read_text())
            except (json.JSONDecodeError, OSError):
                pass
        dumps.append(info)

    dumps.sort(key=lambda d: d["modified_at"], reverse=True)
    return dumps


# ── internal helpers ──────────────────────────────────────────────────


def _run_alembic_after_pg_restore() -> None:
    """Apply pending Alembic revisions so restored data matches current ORM.

    ``pg_restore`` replays DDL from the backup file. Older dumps predate columns
    such as ``users.email``; the running app still issues SELECTs for those
    columns. ``alembic upgrade head`` only **adds** missing schema (indexes,
    columns, constraints). It does **not** delete user rows or truncate tables.

    Organization seeding is **disabled** here so an import stays faithful to the
    dump: we do not inject demo organizations when the restored ``organizations``
    table happens to be empty.
    """
    init_db(seed_organizations=False)


def _reset_all_sequences(pg_engine: Engine) -> None:
    """Reset all serial sequences to max(id)+1."""
    pg_inspector = inspect(pg_engine)
    with pg_engine.begin() as conn:
        for table in pg_inspector.get_table_names():
            seq_name = f"{table}_id_seq"
            try:
                conn.execute(text(f"SELECT setval('{seq_name}', COALESCE((SELECT MAX(id) FROM \"{table}\"), 1))"))
            except DATABASE_ERRORS:
                pass
