"""
MindGraph database migration / PostgreSQL import CLI.

Loads ``.env`` from the project root automatically (or ``MINDGRAPH_ENV_FILE``
if set).  Set ``MINDGRAPH_MIGRATION_DEBUG=1`` for debug logging (optional).

For PostgreSQL, after loading ``.env`` the script tries to ensure the server is
reachable (same logic as ``dump_import_postgres.ensure_postgresql_running``):
if the database does not accept connections, it may start PostgreSQL via the
app starter, ``systemctl``, or Windows services — but not when failure is
password authentication (server already running).

- **Run Alembic migrations**: executes ``alembic upgrade head`` to apply all
  pending schema changes.
- **Import backup**: if any expected tables are missing, runs ``alembic
  upgrade head`` (schema only) before ``pg_restore``.  Then restores from
  ``BACKUP_DIR`` (default ``backup/``), same rules as
  ``scripts/db/dump_import_postgres.py`` — each
  ``mindgraph.postgresql.*.dump`` needs a ``*.dump.manifest.json`` beside it.

Usage:
    python scripts/db/run_migrations.py

Copyright 2024-2025 Beijing Siyuan Zhijiao Technology Co., Ltd.
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import importlib
import importlib.util
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict
from urllib.parse import urlparse, urlunparse

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("PYTHONPATH", str(PROJECT_ROOT))

_DEFAULT_ENV_PATH = PROJECT_ROOT / ".env"


def _ensure_public_schema_for_project_db(mods: Dict[str, Any]) -> bool:
    """Ensure ``public`` schema exists before ORM DDL."""
    prep = importlib.import_module("services.utils.pg_restore_prep")
    ensure_fn = getattr(prep, "ensure_public_schema_exists")
    return bool(ensure_fn(mods["DATABASE_URL"], mods["engine"]))


def _resolve_env_path() -> Path:
    """Project ``.env``, or ``MINDGRAPH_ENV_FILE`` when set."""
    env_override = os.getenv("MINDGRAPH_ENV_FILE")
    if env_override:
        path = Path(env_override).expanduser()
        return path if path.is_absolute() else (PROJECT_ROOT / path).resolve()
    return _DEFAULT_ENV_PATH


def _apply_env_file(path: Path) -> None:
    """Load KEY=VALUE pairs into os.environ if not already set (bootstrap)."""
    if not path.is_file():
        return
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return
    for raw_line in raw.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = val


if sys.platform != "win32":
    try:
        uid_zero = hasattr(os, "geteuid") and os.geteuid() == 0
        if uid_zero and not os.getenv("POSTGRESQL_DATA_DIR"):
            try:
                with open("/etc/os-release", "r", encoding="utf-8") as os_file:
                    os_release = os_file.read().lower()
                if "ubuntu" in os_release or "debian" in os_release:
                    os.environ["POSTGRESQL_DATA_DIR"] = "/var/lib/postgresql/mindgraph"
            except (FileNotFoundError, OSError, PermissionError):
                pass
    except (AttributeError, OSError):
        pass


def _mask_database_url(url: str) -> str:
    """Redact password for logs."""
    try:
        parsed = urlparse(url)
        if not parsed.password:
            return url
        user = parsed.username or ""
        host = parsed.hostname or ""
        port = f":{parsed.port}" if parsed.port else ""
        netloc = f"{user}:****@{host}{port}"
        masked = parsed._replace(netloc=netloc)
        return urlunparse(masked)
    except (ValueError, TypeError, AttributeError):
        return url


def _preflight_database(db_engine: Engine) -> None:
    """Fail fast if PostgreSQL is unreachable."""
    with db_engine.connect() as conn:
        conn.execute(text("SELECT 1"))


def _log_database_connection_failure(logger: logging.Logger, exc: Exception) -> None:
    """Log connection failure with hints for common PostgreSQL cases."""
    logger.error("Database connection failed: %s", exc, exc_info=True)
    msg_lower = str(exc).lower()
    if "password authentication failed" in msg_lower:
        logger.error(
            "PostgreSQL rejected the password for this DATABASE_URL. "
            "Set the password in .env (or MINDGRAPH_ENV_FILE) to match the "
            "role on your server, or reset the role: "
            "ALTER ROLE mindgraph_user WITH PASSWORD 'your_secret'; "
            'Test with: psql "postgresql://mindgraph_user:...@localhost:5432/mindgraph" -c "SELECT 1"'
        )
        return
    if "connection refused" in msg_lower:
        logger.error(
            "Nothing accepted the connection on that host/port. "
            "Start PostgreSQL and confirm DATABASE_URL host and port."
        )
        return
    logger.error("Check DATABASE_URL, PostgreSQL service, and network/firewall settings.")


def _configure_logging(debug: bool) -> None:
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="[%(asctime)s] %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _check_status(db_engine: Engine, base: Any) -> None:
    """Log expected vs existing tables."""
    logger = logging.getLogger(__name__)
    logger.info("%s", "=" * 60)
    logger.info("STEP 1: CHECK — current database status")
    logger.info("%s", "=" * 60)

    expected_tables = set(base.metadata.tables.keys())
    inspector = inspect(db_engine)
    existing_tables = set(inspector.get_table_names())
    missing_tables = expected_tables - existing_tables

    logger.info(
        "Expected tables: %d  |  Existing: %d  |  Missing: %d",
        len(expected_tables),
        len(existing_tables),
        len(missing_tables),
    )

    if missing_tables:
        logger.warning("Missing table(s):")
        for table_name in sorted(missing_tables):
            logger.warning("  - %s", table_name)
    else:
        logger.info("All expected tables exist in the database")


def _prompt_yes_no(question: str, default_yes: bool) -> bool:
    hint = "Y/n" if default_yes else "y/N"
    raw = input(f"{question} [{hint}]: ").strip().lower()
    if not raw:
        return default_yes
    return raw in ("y", "yes")


def _resolve_backup_dir() -> Path:
    """Same resolution as scripts/db/dump_import_postgres (BACKUP_DIR in .env)."""
    raw = os.getenv("BACKUP_DIR", "backup")
    path = Path(raw)
    return path if path.is_absolute() else PROJECT_ROOT / path


def _load_dump_import_module() -> Any:
    """Load dump_import_postgres without requiring scripts/ to be a package."""
    path = PROJECT_ROOT / "scripts" / "db" / "dump_import_postgres.py"
    name = "mindgraph_dump_import_postgres"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _ensure_postgresql_for_migrations(db_url: str) -> bool:
    """If PostgreSQL is not reachable, try starting it."""
    logger = logging.getLogger(__name__)
    try:
        dip = _load_dump_import_module()
    except RuntimeError as exc:
        logger.error("%s", exc)
        return False
    return bool(dip.ensure_postgresql_running(db_url))


def _prompt_primary_mode() -> str:
    """Return 'migrations', 'import_pg', or 'quit'."""
    print()
    print("What do you want to do?")
    print("  1) Run Alembic migrations (alembic upgrade head)")
    print("  2) Import backup into PostgreSQL (mindgraph.postgresql.*.dump)")
    print("  3) Quit")
    while True:
        choice = input("Enter 1, 2, or 3: ").strip()
        if choice == "1":
            return "migrations"
        if choice == "2":
            return "import_pg"
        if choice == "3":
            return "quit"
        print("Please enter 1, 2, or 3.")


def _load_database_modules() -> Dict[str, Any]:
    """Import DB stack after .env has been applied."""
    cfg = importlib.import_module("config.database")
    return {
        "Base": cfg.Base,
        "DATABASE_URL": cfg.DATABASE_URL,
        "engine": cfg.engine,
        "init_db": cfg.init_db,
    }


def _connect_and_report(mods: Dict[str, Any], env_path: Path) -> bool:
    """Preflight DB and log connection summary. Returns False on failure."""
    logger = logging.getLogger(__name__)
    logger.info(
        "Env file: %s",
        env_path.resolve() if env_path.exists() else "(not found)",
    )
    logger.info("Database URL: %s", _mask_database_url(mods["DATABASE_URL"]))
    logger.info("Dialect: %s", mods["engine"].dialect.name)
    try:
        _preflight_database(mods["engine"])
    except Exception as exc:
        _log_database_connection_failure(logger, exc)
        return False
    return True


def _run_apply_flow(mods: Dict[str, Any]) -> int:
    """Run Alembic migrations and seed data via init_db()."""
    logger = logging.getLogger(__name__)
    base = mods["Base"]
    logger.info(
        "Registered %d table(s) on Base.metadata",
        len(base.metadata.tables),
    )
    _check_status(mods["engine"], base)

    print()
    if not _prompt_yes_no("Proceed with alembic upgrade head", default_yes=False):
        print("Cancelled.")
        return 0

    if mods["engine"].dialect.name == "postgresql":
        if not _ensure_public_schema_for_project_db(mods):
            logger.error("Could not ensure schema public; fix the database and retry.")
            return 1

    logger.info("%s", "=" * 60)
    logger.info("APPLY — init_db (alembic upgrade + seed)")
    logger.info("%s", "=" * 60)

    try:
        mods["init_db"](seed_organizations=True)
    except Exception as exc:
        logger.error("init_db() failed: %s", exc, exc_info=True)
        return 1

    logger.info("Migration and seeding completed successfully")
    return 0


def _ensure_schema_before_pg_import(mods: Dict[str, Any], live: bool) -> bool:
    """Create missing tables via Alembic before pg_restore."""
    logger = logging.getLogger(__name__)
    base = mods["Base"]
    inspector = inspect(mods["engine"])
    existing = set(inspector.get_table_names())
    expected = set(base.metadata.tables.keys())
    missing = expected - existing

    if not missing:
        logger.info("Import precheck: all expected tables exist in the database")
        return True

    logger.warning(
        "Import precheck: %d expected table(s) missing from the database",
        len(missing),
    )
    for table_name in sorted(missing)[:25]:
        logger.warning("  - %s", table_name)
    if len(missing) > 25:
        logger.warning("  ... and %d more", len(missing) - 25)

    if not live:
        logger.info("[DRY RUN] On execute, init_db would run first to create tables.")
        return True

    if not _ensure_public_schema_for_project_db(mods):
        logger.error("Could not ensure schema public; fix the database and retry.")
        return False

    logger.info("Creating missing schema (init_db, seed_organizations=False) before pg_restore...")
    try:
        mods["init_db"](seed_organizations=False)
    except Exception as exc:
        logger.error("init_db() failed before import: %s", exc, exc_info=True)
        return False

    inspector_after = inspect(mods["engine"])
    existing_after = set(inspector_after.get_table_names())
    still_missing = expected - existing_after
    if still_missing:
        logger.error(
            "After alembic upgrade, %d table(s) still missing: %s",
            len(still_missing),
            ", ".join(sorted(still_missing)[:15]),
        )
        return False
    logger.info("Import precheck: schema ready for pg_restore")
    return True


def _run_pg_import_flow(mods: Dict[str, Any]) -> int:
    """pg_restore from backup/ using manifest verification."""
    logger = logging.getLogger(__name__)
    if mods["engine"].dialect.name != "postgresql":
        logger.error(
            "PostgreSQL dump import needs DATABASE_URL to be PostgreSQL. Current dialect: %s",
            mods["engine"].dialect.name,
        )
        return 1

    backup_dir = _resolve_backup_dir()
    logger.info("Backup folder (BACKUP_DIR): %s", backup_dir.resolve())
    print()
    print(
        "Each dump file must have a manifest in the same folder, e.g.\n"
        "  mindgraph.postgresql.YYYYMMDD_HHMMSS.dump\n"
        "  mindgraph.postgresql.YYYYMMDD_HHMMSS.dump.manifest.json"
    )
    print("Stop the MindGraph app before choosing Execute.")

    try:
        dip = _load_dump_import_module()
    except RuntimeError as exc:
        logger.error("%s", exc)
        return 1

    live = dip.prompt_dry_run_or_execute()
    if live:
        logger.info("Execute mode — pg_restore will replace data in the target DB")
    else:
        logger.info("Dry run — no changes")

    if not _ensure_schema_before_pg_import(mods, live):
        return 1

    return dip.import_command(
        live,
        db_url=mods["DATABASE_URL"],
        db_engine=mods["engine"],
        backup_dir=backup_dir,
    )


def _interactive_migration_flow(mods: Dict[str, Any]) -> int:
    """After DB connect: run alembic or import backup."""
    primary = _prompt_primary_mode()
    if primary == "quit":
        print("Goodbye.")
        return 0
    if primary == "import_pg":
        return _run_pg_import_flow(mods)
    return _run_apply_flow(mods)


def main() -> int:
    """Load ``.env`` automatically, then prompt for alembic upgrade vs import backup."""
    print("=" * 60)
    print("MindGraph — database migration / PostgreSQL import")
    print("=" * 60)

    env_path = _resolve_env_path()
    _apply_env_file(env_path)

    debug = os.getenv("MINDGRAPH_MIGRATION_DEBUG", "").lower() in (
        "1",
        "true",
        "yes",
    )
    _configure_logging(debug)

    mods = _load_database_modules()
    if mods["engine"].dialect.name == "postgresql":
        if not _ensure_postgresql_for_migrations(mods["DATABASE_URL"]):
            return 1
    if not _connect_and_report(mods, env_path):
        return 1

    return _interactive_migration_flow(mods)


if __name__ == "__main__":
    sys.exit(main())
