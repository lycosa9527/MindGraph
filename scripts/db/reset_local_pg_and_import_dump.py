"""
Drop the local ``mindgraph`` database, sync RLS role passwords from ``.env``,
and import the newest ``backup/mindgraph.postgresql.*.dump``.

Requires ``sudo -u postgres`` (WSL/Linux) or ``PG_ADMIN_URL`` in ``.env``.

Usage (repo root):

    PYTHONPATH=. python scripts/db/reset_local_pg_and_import_dump.py
    PYTHONPATH=. python scripts/db/reset_local_pg_and_import_dump.py --write-sql
    PYTHONPATH=. python scripts/db/reset_local_pg_and_import_dump.py --import-only
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from sqlalchemy.engine import make_url

from utils.db_rls.roles_sql import (
    build_create_roles_sql,
    build_ensure_postgresql_extensions_sql,
    build_grants_sql,
    build_migrate_database_privileges_sql,
)
from scripts.db import dump_import_postgres as dip
from scripts.db import rls_roles_bootstrap as rls_boot
from scripts.db._path_setup import project_root
from scripts.db.migration_urls import (
    ROLE_MIGRATE,
    build_role_url,
    configure_rls_migration_environment,
    create_migration_engine,
    normalise_db_url,
)

logger = logging.getLogger(__name__)

DB_NAME = "mindgraph"
SQL_DIR = Path("/tmp/mindgraph_pg_reset")
STEP1_SQL = SQL_DIR / "01_drop_create_database.sql"
STEP2_SQL = SQL_DIR / "02_bootstrap_roles.sql"


def _sql_escape(value: str) -> str:
    return value.replace("'", "''")


def _passwords_from_env() -> tuple[str, str]:
    app_url = make_url(os.environ["DATABASE_URL"])
    migrate_url = make_url(os.environ["DATABASE_MIGRATION_URL"])
    app_password = app_url.password or ""
    migrate_password = migrate_url.password or ""
    if not app_password or not migrate_password:
        raise RuntimeError("DATABASE_URL and DATABASE_MIGRATION_URL must include passwords in .env")
    return app_password, migrate_password


def _build_drop_recreate_database_sql() -> str:
    return f"""
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = '{DB_NAME}' AND pid <> pg_backend_pid();
DROP DATABASE IF EXISTS {DB_NAME};
CREATE DATABASE {DB_NAME};
"""


def _build_bootstrap_sql(app_password: str, migrate_password: str) -> str:
    sync = f"""
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mindgraph_app') THEN
        ALTER ROLE mindgraph_app WITH LOGIN PASSWORD '{_sql_escape(app_password)}';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mindgraph_migrate') THEN
        ALTER ROLE mindgraph_migrate WITH LOGIN PASSWORD '{_sql_escape(migrate_password)}';
        ALTER ROLE mindgraph_migrate BYPASSRLS;
    END IF;
END $$;
"""
    return (
        sync
        + build_create_roles_sql(app_password, migrate_password)
        + "\n"
        + build_grants_sql()
        + "\n"
        + build_migrate_database_privileges_sql()
        + "\n"
        + build_ensure_postgresql_extensions_sql()
    )


def _write_sql_files() -> None:
    app_password, migrate_password = _passwords_from_env()
    SQL_DIR.mkdir(parents=True, exist_ok=True)
    STEP1_SQL.write_text(_build_drop_recreate_database_sql().strip() + "\n", encoding="utf-8")
    STEP2_SQL.write_text(_build_bootstrap_sql(app_password, migrate_password).strip() + "\n", encoding="utf-8")
    logger.info("Wrote %s", STEP1_SQL)
    logger.info("Wrote %s", STEP2_SQL)


def _print_manual_sudo_steps() -> None:
    print("\nRun these in WSL (enter your Linux password when sudo prompts):\n")
    print(f"  sudo -u postgres psql -v ON_ERROR_STOP=1 -f {STEP1_SQL}")
    print(f"  sudo -u postgres psql -v ON_ERROR_STOP=1 -d {DB_NAME} -f {STEP2_SQL}")
    print("\nThen import the production dump:\n")
    print("  PYTHONPATH=. python scripts/db/reset_local_pg_and_import_dump.py --import-only\n")


def _reset_database_and_roles() -> None:
    run_sudo_postgres_psql = getattr(rls_boot, "_run_sudo_postgres_psql")
    verify_roles_created = getattr(rls_boot, "_verify_roles_created")
    app_password, migrate_password = _passwords_from_env()
    logger.info("Dropping and recreating database %s (data will be erased)", DB_NAME)
    ok, detail = run_sudo_postgres_psql(
        "postgres",
        _build_drop_recreate_database_sql(),
        allow_password_prompt=True,
    )
    if not ok:
        _write_sql_files()
        raise RuntimeError(
            f"Could not recreate database {DB_NAME}: {detail}. "
            f"SQL files written under {SQL_DIR} — run the manual sudo steps below."
        )

    logger.info("Syncing RLS roles and grants from .env passwords")
    ok, detail = run_sudo_postgres_psql(
        DB_NAME,
        _build_bootstrap_sql(app_password, migrate_password),
        allow_password_prompt=True,
    )
    if not ok:
        raise RuntimeError(f"Could not bootstrap RLS roles on {DB_NAME}: {detail}")

    if not verify_roles_created(normalise_db_url(os.environ["DATABASE_URL"])):
        raise RuntimeError(
            "Roles were bootstrapped but mindgraph_app / mindgraph_migrate login still failed. "
            "Check DATABASE_URL / DATABASE_MIGRATION_URL passwords in .env"
        )
    logger.info("PostgreSQL ready: %s with .env credentials", DB_NAME)


def _import_latest_dump() -> int:
    configure_rls_migration_environment()

    migrate_url = os.environ.get("DATABASE_MIGRATION_URL") or build_role_url(os.environ["DATABASE_URL"], ROLE_MIGRATE)
    migration_engine = create_migration_engine(migrate_url)

    backup_dir = Path(os.getenv("BACKUP_DIR", "backup"))
    if not backup_dir.is_absolute():
        backup_dir = Path(__file__).resolve().parents[2] / backup_dir

    dumps = dip.list_dumps(backup_dir)
    if not dumps:
        raise RuntimeError(f"No dump files in {backup_dir}")

    dump_path = dumps[0]
    logger.info("Importing %s", dump_path.name)

    setattr(dip, "_confirm_overwrite", lambda *_args, **_kwargs: True)
    dip.select_dump_file = lambda backup_dir=None: dumps[0]

    prepare_pg_dump_cli = getattr(dip, "_prepare_pg_dump_cli")
    prep_err = prepare_pg_dump_cli()
    if prep_err is not None:
        return prep_err

    return dip.import_command(
        live=True,
        db_url=migrate_url,
        db_engine=migration_engine,
        backup_dir=backup_dir,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reset local PostgreSQL and import production dump")
    parser.add_argument(
        "--write-sql",
        action="store_true",
        help="Write sudo SQL files to scripts/db/.local_pg_reset/ and print manual steps",
    )
    parser.add_argument(
        "--import-only",
        action="store_true",
        help="Skip database reset; import the newest backup dump only",
    )
    return parser.parse_args()


def main() -> int:
    """CLI entry: optional SQL write, database reset, then dump import."""
    args = _parse_args()
    os.chdir(project_root)
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    print("=" * 60)
    print("MindGraph — reset local PostgreSQL and import production dump")
    print("=" * 60)

    if args.write_sql:
        _write_sql_files()
        _print_manual_sudo_steps()
        return 0

    if not args.import_only:
        print("This ERASES the local mindgraph database and reloads from backup/.")
        print("Enter your Linux password when sudo prompts.\n")

    try:
        if not args.import_only:
            _reset_database_and_roles()
        return _import_latest_dump()
    except RuntimeError as exc:
        logger.error("%s", exc)
        if STEP1_SQL.is_file():
            _print_manual_sudo_steps()
        return 1


if __name__ == "__main__":
    sys.exit(main())
