"""
Temporary staging schema for PG dump analysis and merge.

Restores dumps into an isolated schema on the live database so the migrate
role does not need CREATEDB or a separate admin connection.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
import re
import subprocess
import tempfile
import uuid as uuid_mod
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional, Tuple

import psycopg
from psycopg import sql as psycopg_sql
from sqlalchemy import create_engine, event, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.pool import NullPool

from services.utils.error_types import DATABASE_ERRORS, PG_CONNECT_ERRORS
from services.utils.pg_client_binaries import find_pg_client_binary

logger = logging.getLogger(__name__)

_STAGING_PREFIX = "mindgraph_merge_staging_"
_RESTORE_TIMEOUT_SECONDS = 3600
_PUBLIC_SCHEMA = "public"

# pg_restore may still emit cluster/database globals; never replay these in staging.
_SKIP_LINE_PREFIXES = (
    "ALTER DATABASE",
    "COMMENT ON DATABASE",
    "CREATE EVENT TRIGGER",
    "ALTER EVENT TRIGGER",
    "DROP EVENT TRIGGER",
    "CREATE EXTENSION",
    "COMMENT ON EXTENSION",
    "ALTER EXTENSION",
    "DROP EXTENSION",
    "CREATE PUBLICATION",
    "ALTER PUBLICATION",
    "DROP PUBLICATION",
    "CREATE SUBSCRIPTION",
    "ALTER SUBSCRIPTION",
    "DROP SUBSCRIPTION",
    "CREATE SCHEMA public",
    "COMMENT ON SCHEMA public",
    "ALTER SCHEMA public",
    "ALTER DEFAULT PRIVILEGES",
    "SECURITY LABEL",
    "\\connect",
    "\\restrict",
    "\\unrestrict",
)

_PSQL_ERROR_LINE = re.compile(r"ERROR:\s*(.+)", re.IGNORECASE)


@dataclass(frozen=True)
class StagingArea:
    """Live-database URL plus an isolated schema holding restored dump objects."""

    db_url: str
    schema_name: str


def _sqla_url(libpq_url: str) -> str:
    if libpq_url.startswith("postgresql://"):
        return "postgresql+psycopg://" + libpq_url[len("postgresql://") :]
    return libpq_url


def _skip_restore_line(line: str) -> bool:
    """Return True when a pg_restore SQL line should not run in staging."""
    stripped = line.strip()
    if not stripped or stripped.startswith("--"):
        return False
    if any(stripped.startswith(prefix) for prefix in _SKIP_LINE_PREFIXES):
        return True
    if stripped.startswith("GRANT ") or stripped.startswith("REVOKE "):
        return True
    if " ON SCHEMA public" in line and ("GRANT" in line or "REVOKE" in line):
        return True
    return False


def _rewrite_restore_line(line: str, schema: str) -> Optional[str]:
    """Map public-schema DDL/DML from pg_restore into *schema*."""
    if _skip_restore_line(line):
        return None
    quoted = f'"{schema}"'
    rewritten = line.replace(f"SCHEMA {_PUBLIC_SCHEMA}", f"SCHEMA {quoted}")
    rewritten = rewritten.replace(f"{_PUBLIC_SCHEMA}.", f"{quoted}.")
    rewritten = rewritten.replace(f"search_path = {_PUBLIC_SCHEMA}", f"search_path = {quoted}")
    rewritten = rewritten.replace(f"search_path={_PUBLIC_SCHEMA}", f"search_path={quoted}")
    rewritten = rewritten.replace(
        f"'search_path', '{_PUBLIC_SCHEMA}'",
        f"'search_path', '{schema}'",
    )
    return rewritten


def _iter_rewritten_sql(raw_lines: Iterator[str], schema: str) -> Iterator[str]:
    for line in raw_lines:
        rewritten = _rewrite_restore_line(line, schema)
        if rewritten is not None:
            yield rewritten


def _format_psql_error(stderr: str, fallback: str = "psql restore failed") -> str:
    """Extract a concise ERROR line from psql stderr."""
    for raw_line in stderr.splitlines():
        match = _PSQL_ERROR_LINE.search(raw_line)
        if match:
            return match.group(1).strip()[:500]
    cleaned = stderr.strip()
    return cleaned[:500] if cleaned else fallback


def cleanup_orphan_staging_schemas(db_url: str) -> int:
    """Drop leftover merge staging schemas from interrupted analyze/merge runs."""
    pattern = _STAGING_PREFIX + "%"
    dropped = 0
    try:
        with psycopg.connect(db_url, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT schema_name FROM information_schema.schemata "
                    "WHERE schema_name LIKE %s",
                    (pattern,),
                )
                orphan_names = [row[0] for row in cur.fetchall()]
                for schema_name in orphan_names:
                    cur.execute(
                        psycopg_sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(
                            psycopg_sql.Identifier(schema_name)
                        )
                    )
                    dropped += 1
    except PG_CONNECT_ERRORS as exc:
        logger.warning("[PGMerge] Orphan staging schema cleanup failed: %s", exc)
        return dropped

    if dropped:
        logger.info("[PGMerge] Cleaned up %d orphan staging schema(s)", dropped)
    return dropped


def _write_rewritten_restore_sql(
    dump_path: str,
    schema: str,
    pg_restore: str,
    sql_path: Path,
) -> Tuple[bool, str, int]:
    """Run pg_restore and write schema-remapped SQL to *sql_path*."""
    with subprocess.Popen(
        [
            pg_restore,
            "--no-owner",
            "--no-acl",
            "-n",
            _PUBLIC_SCHEMA,
            "-f",
            "-",
            dump_path,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    ) as restore_proc:
        assert restore_proc.stdout is not None
        data_line_count = 0
        with sql_path.open("w", encoding="utf-8") as sql_file:
            sql_file.write(f'SET search_path TO "{schema}";\n')
            for rewritten in _iter_rewritten_sql(restore_proc.stdout, schema):
                sql_file.write(rewritten)
                data_line_count += 1

        restore_stderr = restore_proc.stderr.read() if restore_proc.stderr else ""
        restore_code = restore_proc.wait()

    if restore_code > 1:
        detail = restore_stderr[:500] or f"pg_restore exit code {restore_code}"
        return False, detail, data_line_count

    if data_line_count == 0:
        detail = restore_stderr[:500] or "pg_restore produced no restorable SQL for public schema"
        return False, detail, data_line_count

    if restore_code == 1:
        logger.warning(
            "[PGMerge] pg_restore completed with warnings: %s",
            restore_stderr[:500],
        )

    return True, restore_stderr, data_line_count


def create_staging_area(db_url: str) -> StagingArea:
    """Create an empty staging schema on the live database."""
    schema_name = _STAGING_PREFIX + uuid_mod.uuid4().hex[:8]
    with psycopg.connect(db_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                psycopg_sql.SQL("CREATE SCHEMA {}").format(psycopg_sql.Identifier(schema_name))
            )
    logger.info("[PGMerge] Created staging schema: %s", schema_name)
    return StagingArea(db_url=db_url, schema_name=schema_name)


def restore_dump_to_staging(area: StagingArea, dump_path: str) -> Tuple[bool, str]:
    """Load a custom-format dump into the staging schema via pg_restore → psql."""
    pg_restore = find_pg_client_binary("pg_restore")
    psql = find_pg_client_binary("psql")
    if not pg_restore:
        return False, "pg_restore not found on system PATH"
    if not psql:
        return False, "psql not found on system PATH"

    if not Path(dump_path).is_file():
        return False, f"Dump file not found: {dump_path}"

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".sql",
        delete=False,
        encoding="utf-8",
    ) as sql_tmp:
        sql_path = Path(sql_tmp.name)

    psql_result: subprocess.CompletedProcess[str] | None = None
    detail = ""
    try:
        ok, detail, _line_count = _write_rewritten_restore_sql(
            dump_path,
            area.schema_name,
            pg_restore,
            sql_path,
        )
        if not ok:
            logger.error("[PGMerge] pg_restore failed: %s", detail)
            return False, detail

        psql_result = subprocess.run(
            [
                psql,
                "-v",
                "ON_ERROR_STOP=1",
                "-1",
                "-q",
                "-f",
                str(sql_path),
                "-d",
                area.db_url,
            ],
            capture_output=True,
            text=True,
            timeout=_RESTORE_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return False, f"Restore timed out after {_RESTORE_TIMEOUT_SECONDS}s"
    finally:
        sql_path.unlink(missing_ok=True)

    if psql_result is None:
        return False, detail or "psql restore did not start"

    if psql_result.returncode != 0:
        message = _format_psql_error(
            psql_result.stderr or psql_result.stdout or "",
            fallback=detail or "psql restore failed",
        )
        logger.error("[PGMerge] psql restore failed (exit %d): %s", psql_result.returncode, message)
        return False, message

    logger.info("[PGMerge] Restored dump into staging schema %s", area.schema_name)
    return True, ""


def drop_staging_area(area: StagingArea) -> None:
    """Drop the staging schema and all restored objects."""
    try:
        with psycopg.connect(area.db_url, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    psycopg_sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(
                        psycopg_sql.Identifier(area.schema_name)
                    )
                )
        logger.info("[PGMerge] Dropped staging schema: %s", area.schema_name)
    except PG_CONNECT_ERRORS as exc:
        logger.warning(
            "[PGMerge] Failed to drop staging schema %s: %s",
            area.schema_name,
            exc,
        )


def staging_engine(area: StagingArea) -> Engine:
    """SQLAlchemy engine whose connections default to the staging schema."""
    engine = create_engine(_sqla_url(area.db_url), poolclass=NullPool)

    @event.listens_for(engine, "connect")
    def _set_search_path(dbapi_connection, _connection_record) -> None:
        with dbapi_connection.cursor() as cursor:
            cursor.execute(
                psycopg_sql.SQL("SET search_path TO {}").format(
                    psycopg_sql.Identifier(area.schema_name)
                )
            )

    return engine


def staging_table_names(engine: Engine, schema: str) -> set[str]:
    """Return table names visible in the staging schema."""
    inspector = inspect(engine)
    try:
        return set(inspector.get_table_names(schema=schema))
    except DATABASE_ERRORS:
        return set()


def merge_database_engine(db_url: str) -> Engine:
    """Disposable engine for live DB reads/writes during admin merge (migrate / BYPASSRLS)."""
    return create_engine(_sqla_url(db_url), poolclass=NullPool)
