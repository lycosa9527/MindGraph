"""
MindGraph database migration / PostgreSQL import CLI.

Loads ``.env`` from the project root automatically (or ``MINDGRAPH_ENV_FILE``
if set).  Set ``MINDGRAPH_MIGRATION_DEBUG=1`` for debug logging (optional).

For PostgreSQL, after loading ``.env`` the script tries to ensure the server is
reachable (same logic as ``dump_import_postgres.ensure_postgresql_running``):
if the database does not accept connections, it may start PostgreSQL via the
app starter, ``systemctl``, or Windows services — but not when failure is
password authentication (server already running).

RLS is mandatory: the script sets ``DATABASE_MIGRATION_URL`` automatically
(``mindgraph_migrate`` or ``mindgraph_user``) before Alembic runs, even when
``.env`` already points ``DATABASE_URL`` at ``mindgraph_app``.

- **Run Alembic migrations** (menu 1): ``alembic upgrade head`` only.
- **Check status** (menu 3): revision + RLS check, optional ``.env`` patch, Redis flush.
- **Full local setup** (menu 4): bootstrap RLS roles when missing, migrate to head,
  patch ``DATABASE_URL`` / ``DATABASE_MIGRATION_URL`` in ``.env``, optional Redis flush.
- **Import backup**: if any expected tables are missing, runs ``alembic
  upgrade head`` (schema only) before ``pg_restore``.  Then restores from
  ``BACKUP_DIR`` (default ``backup/``), same rules as
  ``scripts/db/dump_import_postgres.py`` — each
  ``mindgraph.postgresql.*.dump`` needs a ``*.dump.manifest.json`` beside it.

Usage:
    python scripts/db/run_migrations.py

Menu option 4 runs the full local dev path: RLS roles (if missing), alembic upgrade
head, patch ``.env`` with ``mindgraph_app`` / ``mindgraph_migrate``, optional Redis flush.

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
from sqlalchemy.engine import Engine, make_url

from scripts.db.migration_urls import (
    RLS_HEAD_REVISION,
    ROLE_APP,
    configure_rls_migration_environment,
    create_migration_engine,
    env_rls_database_urls_match,
    first_connectable_database_url,
    print_rls_post_migration_guidance,
    update_env_rls_database_urls,
    verify_rls_migration_complete,
)
from scripts.db.pg_ensure import ensure_postgresql_running, ensure_postgresql_server_reachable
from scripts.db.redis_flush import flush_redis_cache, redis_flush_cli_hint, redis_flush_summary_label
from scripts.db.rls_roles_bootstrap import ensure_rls_roles_exist, iter_bootstrap_guidance, try_bootstrap_rls_roles
from services.utils.error_types import DATABASE_ERRORS

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("PYTHONPATH", str(PROJECT_ROOT))

_DEFAULT_ENV_PATH = PROJECT_ROOT / ".env"


def _ensure_public_schema_for_project_db(mods: Dict[str, Any]) -> bool:
    """Ensure ``public`` schema exists before ORM DDL."""
    prep = importlib.import_module("services.utils.pg_restore_prep")
    ensure_fn = getattr(prep, "ensure_public_schema_exists")
    return bool(ensure_fn(mods["DATABASE_MIGRATION_URL"], mods["migration_engine"]))


def _resolve_env_path() -> Path:
    """Project ``.env``, or ``MINDGRAPH_ENV_FILE`` when set."""
    env_override = os.getenv("MINDGRAPH_ENV_FILE")
    if env_override:
        path = Path(env_override).expanduser()
        return path if path.is_absolute() else (PROJECT_ROOT / path).resolve()
    return _DEFAULT_ENV_PATH


_ENV_OVERRIDE_KEYS = frozenset(
    {
        "DATABASE_URL",
        "DATABASE_MIGRATION_URL",
        "MINDGRAPH_APP_PASSWORD",
        "MINDGRAPH_MIGRATE_PASSWORD",
        "POSTGRESQL_PASSWORD",
        "PG_ADMIN_URL",
        "REDIS_URL",
    }
)


def _apply_env_file(path: Path) -> None:
    """Load ``.env``; database / RLS keys always win over stale shell exports."""
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
        if not key:
            continue
        if key in _ENV_OVERRIDE_KEYS or key not in os.environ:
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
            "PostgreSQL rejected the password for the migrate URL. "
            "Set MINDGRAPH_MIGRATE_PASSWORD / POSTGRESQL_PASSWORD in .env, or "
            "DATABASE_MIGRATION_URL explicitly. "
            "Reset role example: ALTER ROLE mindgraph_migrate WITH PASSWORD 'your_secret';"
        )
        return
    if "does not exist" in msg_lower and "role" in msg_lower:
        logger.error("Login role missing. Run option 3 (status) to bootstrap mindgraph_app / mindgraph_migrate.")
        return
    if "connection refused" in msg_lower:
        logger.error(
            "Nothing accepted the connection on that host/port. "
            "Start PostgreSQL and confirm DATABASE_URL host and port."
        )
        return
    logger.error("Check DATABASE_URL, DATABASE_MIGRATION_URL, and PostgreSQL service.")


def _configure_logging(debug: bool) -> None:
    """Configure logging."""
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
    """Prompt yes no."""
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
    """If PostgreSQL is not reachable, try starting it (no full app import)."""
    return bool(ensure_postgresql_running(db_url))


def _fetch_alembic_revision(db_engine: Engine) -> str:
    """Fetch alembic revision."""
    with db_engine.connect() as conn:
        row = conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).first()
    return str(row[0]) if row else "(none)"


def _verify_and_bootstrap_rls(db_engine: Engine) -> tuple[bool, list[str]]:
    """Verify RLS rollout; create roles via superuser when rev 0043 skipped them."""
    logger = logging.getLogger(__name__)
    rls_ok, rls_issues = verify_rls_migration_complete(db_engine)
    if rls_ok:
        return True, []
    if not any("role mindgraph_" in issue for issue in rls_issues):
        return False, rls_issues

    boot_ok, boot_msg = try_bootstrap_rls_roles()
    if boot_ok:
        logger.info("%s", boot_msg)
        return verify_rls_migration_complete(db_engine)
    logger.error("%s", boot_msg)
    return False, rls_issues


def _print_migration_rls_status(db_engine: Engine) -> tuple[bool, list[str]]:
    """Print Alembic revision and RLS check summary."""
    revision = _fetch_alembic_revision(db_engine)
    print(f"alembic_version: {revision} (head target for RLS: {RLS_HEAD_REVISION})")

    rls_ok, issues = _verify_and_bootstrap_rls(db_engine)
    if rls_ok:
        print("RLS rollout check: OK")
        return True, []

    print("RLS rollout check: INCOMPLETE")
    for issue in issues:
        print(f"  - {issue}")
    if any("role mindgraph_" in issue for issue in issues):
        print("Fix missing roles:")
        for line in iter_bootstrap_guidance():
            print(f"  {line}")
    return False, issues


def _offer_env_rls_patch(
    db_engine: Engine,
    env_path: Path,
    *,
    patch_default_yes: bool | None = None,
    redis_flush_default_yes: bool = True,
) -> None:
    """Show RLS URL guidance, optionally patch ``.env``, then offer Redis flush."""
    if db_engine.dialect.name != "postgresql":
        return

    rls_ok, _issues = verify_rls_migration_complete(db_engine)
    if not rls_ok:
        return

    print_rls_post_migration_guidance(db_engine, env_path)
    if env_path.is_file():
        already_set = env_rls_database_urls_match(env_path, db_engine)
        if already_set:
            print("  .env already has RLS DATABASE_URL / DATABASE_MIGRATION_URL")
        print()
        patch_default = patch_default_yes if patch_default_yes is not None else not already_set
        if _prompt_yes_no(
            f"Write RLS DATABASE_URL / DATABASE_MIGRATION_URL into {env_path.name}",
            default_yes=patch_default,
        ):
            if update_env_rls_database_urls(env_path, db_engine):
                print(f"  Reload env and start app with {ROLE_APP} on DATABASE_URL.")

    _offer_redis_flush_with_default(redis_flush_default_yes)


def _offer_redis_flush_with_default(default_yes: bool) -> None:
    """Optional ``FLUSHDB`` after RLS URL switch."""
    label = redis_flush_summary_label()
    print()
    if not _prompt_yes_no(f"Flush Redis cache ({label})", default_yes=default_yes):
        print(f"  Skipped Redis flush. Run manually if needed: {redis_flush_cli_hint()}")
        return

    ok, message = flush_redis_cache()
    if ok:
        print(f"  {message}")
        return

    print(f"  Redis flush failed: {message}")
    print(f"  Ensure Redis is running, then: {redis_flush_cli_hint()}")


def _prepare_migration_cli() -> tuple[Engine, Path] | int:
    """Load env, ensure PostgreSQL, resolve migrate URL, return engine + env path."""
    env_path = _resolve_env_path()
    _apply_env_file(env_path)

    debug = os.getenv("MINDGRAPH_MIGRATION_DEBUG", "").lower() in (
        "1",
        "true",
        "yes",
    )
    _configure_logging(debug)

    logger = logging.getLogger(__name__)
    runtime_url = os.getenv("DATABASE_URL", "")
    if "postgresql" in runtime_url.lower():
        connected = first_connectable_database_url()
        if connected is not None:
            if not _ensure_postgresql_for_migrations(connected[0]):
                return 1
        else:
            if not ensure_postgresql_server_reachable(runtime_url):
                return 1
            logger.info(
                "PostgreSQL is up; MindGraph roles not connected yet (RLS bootstrap runs next on a fresh install)"
            )

    roles_ok, roles_msg = ensure_rls_roles_exist()
    if not roles_ok:
        logger.error("RLS role bootstrap failed: %s", roles_msg)
        return 1

    try:
        rls_info = configure_rls_migration_environment()
    except DATABASE_ERRORS as exc:
        logger.error(
            "Could not resolve a migrate-capable DATABASE_MIGRATION_URL: %s",
            exc,
        )
        return 1

    runtime_user = make_url(rls_info["runtime_url"]).username or ""
    if runtime_user == ROLE_APP:
        logger.info(
            "DATABASE_URL uses %s; Alembic will use %s (%s) — RLS DDL does not run as the app role",
            ROLE_APP,
            _mask_database_url(rls_info["migration_url"]),
            rls_info["migration_source"],
        )

    logger.info("Runtime DATABASE_URL (from .env): %s", _mask_database_url(rls_info["runtime_url"]))
    logger.info(
        "Alembic migrate URL: %s (%s)",
        _mask_database_url(rls_info["migration_url"]),
        rls_info["migration_source"],
    )

    if not _preflight_migration_url(rls_info["migration_url"], env_path):
        return 1

    migration_engine = create_migration_engine(rls_info["migration_url"])
    return migration_engine, env_path


def run_status_check() -> int:
    """Status-only entry (menu option 3)."""
    print("=" * 60)
    print("MindGraph — migration / RLS status")
    print("=" * 60)

    prepared = _prepare_migration_cli()
    if isinstance(prepared, int):
        return prepared

    migration_engine, env_path = prepared
    if migration_engine.dialect.name != "postgresql":
        print("DATABASE_URL is not PostgreSQL; nothing to check.")
        return 1

    rls_ok, _issues = _print_migration_rls_status(migration_engine)
    if rls_ok:
        _offer_env_rls_patch(migration_engine, env_path)
        return 0
    return 1


def _run_status_flow(migration_engine: Engine, env_path: Path) -> int:
    """Interactive menu: check revision + RLS and optionally patch ``.env``."""
    logger = logging.getLogger(__name__)
    logger.info("%s", "=" * 60)
    logger.info("CHECK — Alembic revision and RLS rollout")
    logger.info("%s", "=" * 60)

    if migration_engine.dialect.name != "postgresql":
        logger.error("DATABASE_URL is not PostgreSQL.")
        return 1

    rls_ok, _issues = _print_migration_rls_status(migration_engine)
    if not rls_ok:
        return 1

    _offer_env_rls_patch(migration_engine, env_path)
    return 0


def _prompt_primary_mode() -> str:
    """Return 'migrations', 'import_pg', 'status', 'full_setup', or 'quit'."""
    print()
    print("What do you want to do?")
    print("  1) Run Alembic migrations (alembic upgrade head)")
    print("  2) Import backup into PostgreSQL (mindgraph.postgresql.*.dump)")
    print("  3) Check migration / RLS status (patch .env, flush Redis)")
    print("  4) Full local setup (RLS roles if missing, migrate to head, patch .env, Redis)")
    print("  5) Quit")
    while True:
        choice = input("Enter 1, 2, 3, 4, or 5: ").strip()
        if choice == "1":
            return "migrations"
        if choice == "2":
            return "import_pg"
        if choice == "3":
            return "status"
        if choice == "4":
            return "full_setup"
        if choice == "5":
            return "quit"
        print("Please enter 1, 2, 3, 4, or 5.")


def _load_database_modules() -> Dict[str, Any]:
    """Import DB stack after ``DATABASE_MIGRATION_URL`` is configured."""
    cfg = importlib.import_module("config.database")
    migration_url = cfg.DATABASE_MIGRATION_URL
    return {
        "Base": cfg.Base,
        "DATABASE_URL": cfg.DATABASE_URL,
        "DATABASE_MIGRATION_URL": migration_url,
        "engine": cfg.engine,
        "migration_engine": create_migration_engine(migration_url),
        "init_db": cfg.init_db,
    }


def _preflight_migration_url(migration_url: str, env_path: Path) -> bool:
    """Connect with migrate URL only (before loading config.database / LLM stack)."""
    logger = logging.getLogger(__name__)
    logger.info(
        "Env file: %s",
        env_path.resolve() if env_path.exists() else "(not found)",
    )
    try:
        db_engine = create_migration_engine(migration_url)
        _preflight_database(db_engine)
        logger.info("Dialect: %s", db_engine.dialect.name)
    except DATABASE_ERRORS as exc:
        _log_database_connection_failure(logger, exc)
        return False
    return True


def _execute_alembic_upgrade(mods: Dict[str, Any]) -> int:
    """Run init_db (alembic upgrade head + seed) after prechecks."""
    logger = logging.getLogger(__name__)
    if mods["migration_engine"].dialect.name == "postgresql":
        if not _ensure_public_schema_for_project_db(mods):
            logger.error("Could not ensure schema public; fix the database and retry.")
            return 1

    logger.info("%s", "=" * 60)
    logger.info("APPLY — init_db (alembic upgrade + seed)")
    logger.info("%s", "=" * 60)

    try:
        mods["init_db"](seed_organizations=True)
    except DATABASE_ERRORS as exc:
        logger.error("init_db() failed: %s", exc, exc_info=True)
        print(f"\nMigration failed: {exc}", flush=True)
        print(
            "Check logs/postgresql.log and re-run option 3 (status) or 4 (full setup).",
            flush=True,
        )
        return 1

    logger.info("Migration and seeding completed successfully")
    return 0


def _run_apply_flow(mods: Dict[str, Any]) -> int:
    """Run Alembic migrations and seed data via init_db()."""
    logger = logging.getLogger(__name__)
    base = mods["Base"]
    logger.info(
        "Registered %d table(s) on Base.metadata",
        len(base.metadata.tables),
    )
    _check_status(mods["migration_engine"], base)

    print()
    if not _prompt_yes_no("Proceed with alembic upgrade head", default_yes=False):
        print("Cancelled.")
        return 0

    if _execute_alembic_upgrade(mods) != 0:
        return 1

    env_path = _resolve_env_path()
    if mods["migration_engine"].dialect.name == "postgresql":
        rls_ok, issues = _print_migration_rls_status(mods["migration_engine"])
        if not rls_ok:
            for issue in issues:
                logger.error("RLS verification: %s", issue)
            logger.error("Mandatory RLS rollout incomplete. Use menu option 3 (status) after fixing roles.")
            return 1
        _offer_env_rls_patch(mods["migration_engine"], env_path)

    return 0


def _run_full_setup_flow(mods: Dict[str, Any], env_path: Path) -> int:
    """
    Menu option 4: roles (already bootstrapped in prepare), migrate, patch .env, Redis.

    Single confirmation; defaults favor patching .env and flushing Redis afterward.
    """
    logger = logging.getLogger(__name__)
    base = mods["Base"]

    logger.info("%s", "=" * 60)
    logger.info("FULL SETUP — RLS roles, alembic upgrade head, .env patch")
    logger.info("%s", "=" * 60)
    print()
    print("This will:")
    print("  • Create mindgraph_app / mindgraph_migrate if missing (sudo may prompt)")
    print("  • Run alembic upgrade head and seed organizations")
    print("  • Offer to write DATABASE_URL / DATABASE_MIGRATION_URL into .env")
    print("  • Offer to flush Redis (recommended after URL change)")
    print("  • If sudo prompts, enter your Linux password to create database roles")
    print()

    _check_status(mods["migration_engine"], base)

    if not _prompt_yes_no("Proceed with full local setup", default_yes=True):
        print("Cancelled.")
        return 0

    if _execute_alembic_upgrade(mods) != 0:
        return 1

    if mods["migration_engine"].dialect.name != "postgresql":
        return 0

    rls_ok, issues = _print_migration_rls_status(mods["migration_engine"])
    if not rls_ok:
        for issue in issues:
            logger.error("RLS verification: %s", issue)
        logger.error("Full setup incomplete — fix the issues above, then run option 4 again.")
        return 1

    _offer_env_rls_patch(
        mods["migration_engine"],
        env_path,
        patch_default_yes=True,
        redis_flush_default_yes=True,
    )
    print()
    print("Full setup finished. Start the app with: python main.py")
    return 0


def _ensure_schema_before_pg_import(mods: Dict[str, Any], live: bool) -> bool:
    """Create missing tables via Alembic before pg_restore."""
    logger = logging.getLogger(__name__)
    base = mods["Base"]
    inspector = inspect(mods["migration_engine"])
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
    except DATABASE_ERRORS as exc:
        logger.error("init_db() failed before import: %s", exc, exc_info=True)
        return False

    inspector_after = inspect(mods["migration_engine"])
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


def _run_pg_import_flow(mods: Dict[str, Any], env_path: Path) -> int:
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

    restore_url = mods["DATABASE_MIGRATION_URL"]
    logger.info("pg_restore target URL: %s", _mask_database_url(restore_url))
    exit_code = dip.import_command(
        live,
        db_url=restore_url,
        db_engine=mods["migration_engine"],
        backup_dir=backup_dir,
    )
    if exit_code == 0 and live:
        logger.info("Import completed — verifying RLS and offering .env / Redis steps")
        _offer_env_rls_patch(mods["migration_engine"], env_path)
    return exit_code


def _interactive_migration_flow(migration_engine: Engine, env_path: Path) -> int:
    """After DB connect: run alembic, import backup, or check status."""
    primary = _prompt_primary_mode()
    if primary == "quit":
        print("Goodbye.")
        return 0
    if primary == "status":
        return _run_status_flow(migration_engine, env_path)
    mods = _load_database_modules()
    logger = logging.getLogger(__name__)
    logger.info("App runtime URL: %s", _mask_database_url(mods["DATABASE_URL"]))
    if primary == "import_pg":
        return _run_pg_import_flow(mods, env_path)
    if primary == "full_setup":
        return _run_full_setup_flow(mods, env_path)
    return _run_apply_flow(mods)


def main() -> int:
    """Load ``.env`` automatically, then prompt for migrate / import / status."""
    print("=" * 60)
    print("MindGraph — database migration / PostgreSQL import")
    print("=" * 60)

    prepared = _prepare_migration_cli()
    if isinstance(prepared, int):
        return prepared

    migration_engine, env_path = prepared
    return _interactive_migration_flow(migration_engine, env_path)


if __name__ == "__main__":
    sys.exit(main())
