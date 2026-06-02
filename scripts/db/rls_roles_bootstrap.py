"""Bootstrap mindgraph_app / mindgraph_migrate when rev 0043 skipped (no CREATEROLE)."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from typing import Iterable

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.pool import NullPool

from scripts.db.migration_urls import (
    ROLE_APP,
    ROLE_MIGRATE,
    build_role_url,
    first_connectable_database_url,
    _password_for_role,
    _role_exists,
    _runtime_url,
    normalise_db_url,
)
from utils.db.alembic_migration import load_rls_roles_sql

_roles_sql = load_rls_roles_sql()
build_create_roles_sql = _roles_sql.build_create_roles_sql
build_grants_sql = _roles_sql.build_grants_sql
build_migrate_database_privileges_sql = _roles_sql.build_migrate_database_privileges_sql
build_reassign_public_objects_to_migrate_sql = (
    _roles_sql.build_reassign_public_objects_to_migrate_sql
)
build_ensure_migrate_bypassrls_sql = _roles_sql.build_ensure_migrate_bypassrls_sql
build_ensure_postgresql_extensions_sql = _roles_sql.build_ensure_postgresql_extensions_sql

_EXTENSION_NAMES = ("pg_stat_statements", "pg_trgm")

logger = logging.getLogger(__name__)

_DEFAULT_PASSWORD = "mindgraph_password"


def _app_password() -> str:
    return _password_for_role(ROLE_APP, _DEFAULT_PASSWORD)


def _migrate_password() -> str:
    return _password_for_role(ROLE_MIGRATE, _DEFAULT_PASSWORD)


def admin_url_candidates(runtime_url: str | None = None) -> list[str]:
    """URLs that can CREATE ROLE (superuser or PG_ADMIN_URL)."""
    runtime = normalise_db_url(runtime_url or _runtime_url())
    parsed = make_url(runtime)
    host = parsed.host or "localhost"
    port = parsed.port or 5432
    candidates: list[str] = []

    admin = os.getenv("PG_ADMIN_URL", "").strip()
    if admin:
        candidates.append(normalise_db_url(admin))

    postgres_pw = os.getenv("POSTGRESQL_PASSWORD") or os.getenv("PGPASSWORD") or ""
    if postgres_pw:
        candidates.append(
            f"postgresql+psycopg://postgres:{postgres_pw}@{host}:{port}/postgres"
        )

    candidates.append(f"postgresql+psycopg://postgres@{host}:{port}/postgres")

    login_user = os.getenv("USER") or os.getenv("USERNAME") or ""
    if login_user and login_user not in ("postgres", parsed.username or ""):
        candidates.append(f"postgresql+psycopg://{login_user}@{host}:{port}/postgres")

    seen: set[str] = set()
    unique: list[str] = []
    for url in candidates:
        if url not in seen:
            seen.add(url)
            unique.append(url)
    return unique


def bootstrap_rls_roles_with_engine(engine: Engine) -> None:
    """Create roles and grants using an admin-capable connection."""
    with engine.connect() as conn:
        conn.execute(text(build_create_roles_sql(_app_password(), _migrate_password())))
        conn.execute(text(build_grants_sql()))
        conn.execute(text(build_migrate_database_privileges_sql()))
        conn.execute(text(build_reassign_public_objects_to_migrate_sql()))
        conn.commit()


def ensure_migrate_database_privileges(
    runtime_url: str | None = None,
    *,
    allow_password_prompt: bool = True,
) -> tuple[bool, str]:
    """
    Ensure mindgraph_migrate can run DDL (CREATE SCHEMA / Alembic) on the app database.

    Probes with CREATE SCHEMA; on failure applies OWNER + CREATE via sudo postgres.
    """
    probe = first_connectable_database_url(runtime_url)
    if probe is None:
        return False, "No DATABASE_URL candidate could connect"
    base_url, _label = probe
    runtime = normalise_db_url(runtime_url or _runtime_url())
    dbname = make_url(runtime).database or "mindgraph"
    migrate_url = build_role_url(base_url, ROLE_MIGRATE)
    engine = create_engine(migrate_url, poolclass=NullPool)
    schema_ok = False
    try:
        with engine.connect() as conn:
            conn.execute(text("CREATE SCHEMA IF NOT EXISTS public"))
            conn.commit()
        schema_ok = True
    except Exception as exc:
        logger.debug("Migrate DDL probe failed (%s): %s", migrate_url, exc)
    finally:
        engine.dispose()

    if not schema_ok:
        priv_sql = build_migrate_database_privileges_sql()
        ok, detail = _run_sudo_postgres_psql(
            dbname,
            priv_sql,
            allow_password_prompt=allow_password_prompt,
        )
        if not ok:
            return False, f"could not grant database privileges to {ROLE_MIGRATE}: {detail}"

        verify_engine = create_engine(migrate_url, poolclass=NullPool)
        try:
            with verify_engine.connect() as conn:
                conn.execute(text("CREATE SCHEMA IF NOT EXISTS public"))
                conn.commit()
        except Exception as exc:
            return False, f"{ROLE_MIGRATE} still cannot run DDL after sudo grant: {exc}"
        finally:
            verify_engine.dispose()

    own_ok, own_msg = ensure_migrate_owns_public_objects(
        base_url,
        allow_password_prompt=allow_password_prompt,
    )
    if not own_ok:
        return False, own_msg

    return ensure_postgresql_extensions(
        base_url,
        allow_password_prompt=allow_password_prompt,
    )


def _public_tables_need_reassign(connect_url: str) -> bool:
    """True when any public table is not owned by mindgraph_migrate."""
    engine = create_engine(normalise_db_url(connect_url), poolclass=NullPool)
    try:
        with engine.connect() as conn:
            count = conn.execute(
                text(
                    """
                    SELECT COUNT(*)::int FROM pg_tables
                    WHERE schemaname = 'public'
                      AND tableowner IS DISTINCT FROM 'mindgraph_migrate'
                    """
                )
            ).scalar()
        return bool(count and count > 0)
    except Exception as exc:
        logger.debug("Could not list public table owners: %s", exc)
        return True
    finally:
        engine.dispose()


def _migrate_can_enable_rls_on_diagrams(migrate_url: str) -> bool:
    """Probe whether migrate role may run RLS DDL on diagrams (Alembic 0044+)."""
    engine = create_engine(migrate_url, poolclass=NullPool)
    try:
        with engine.connect() as conn:
            exists = conn.execute(
                text(
                    """
                    SELECT 1 FROM pg_class c
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname = 'public' AND c.relname = 'diagrams'
                    """
                )
            ).first()
            if exists is None:
                return True
            enabled = conn.execute(
                text(
                    """
                    SELECT c.relrowsecurity FROM pg_class c
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname = 'public' AND c.relname = 'diagrams'
                    """
                )
            ).scalar()
            if enabled:
                return True
            conn.execute(text("ALTER TABLE public.diagrams ENABLE ROW LEVEL SECURITY"))
            conn.execute(text("ALTER TABLE public.diagrams DISABLE ROW LEVEL SECURITY"))
            conn.commit()
        return True
    except Exception as exc:
        logger.debug("RLS enable probe on diagrams failed: %s", exc)
        return False
    finally:
        engine.dispose()


def _postgresql_extensions_installed(connect_url: str) -> bool:
    """True when both optional extensions from rev 0031 exist."""
    engine = create_engine(normalise_db_url(connect_url), poolclass=NullPool)
    try:
        with engine.connect() as conn:
            count = conn.execute(
                text(
                    """
                    SELECT COUNT(*)::int FROM pg_extension
                    WHERE extname IN ('pg_stat_statements', 'pg_trgm')
                    """
                ),
            ).scalar()
        return count == len(_EXTENSION_NAMES)
    except Exception as exc:
        logger.debug("Could not read pg_extension: %s", exc)
        return False
    finally:
        engine.dispose()


def ensure_postgresql_extensions(
    base_url: str,
    *,
    allow_password_prompt: bool = True,
) -> tuple[bool, str]:
    """
    Create pg_stat_statements and pg_trgm as superuser (app roles cannot).

    Matches Alembic rev 0031 and config.database ``_ensure_pg_extensions``.
    """
    if _postgresql_extensions_installed(base_url):
        return True, "PostgreSQL extensions already installed"

    runtime = normalise_db_url(_runtime_url())
    dbname = make_url(runtime).database or "mindgraph"
    ok, detail = _run_sudo_postgres_psql(
        dbname,
        build_ensure_postgresql_extensions_sql(),
        allow_password_prompt=allow_password_prompt,
    )
    if not ok:
        return False, f"could not CREATE EXTENSION (need superuser): {detail}"

    if _postgresql_extensions_installed(base_url):
        return True, "Installed pg_stat_statements and pg_trgm"
    return False, "Extensions still missing after sudo CREATE EXTENSION"


def ensure_migrate_owns_public_objects(
    base_url: str,
    *,
    allow_password_prompt: bool = True,
) -> tuple[bool, str]:
    """
    Ensure public schema objects are owned by mindgraph_migrate (needed for RLS migrations).
    """
    runtime = normalise_db_url(_runtime_url())
    dbname = make_url(runtime).database or "mindgraph"
    migrate_url = build_role_url(base_url, ROLE_MIGRATE)

    if not _public_tables_need_reassign(base_url):
        if _migrate_can_enable_rls_on_diagrams(migrate_url):
            return True, f"{ROLE_MIGRATE} owns public tables (RLS DDL OK)"
    else:
        logger.info(
            "Reassigning public tables from legacy owners to %s before RLS migrations",
            ROLE_MIGRATE,
        )

    ok, detail = _run_sudo_postgres_psql(
        dbname,
        build_reassign_public_objects_to_migrate_sql(),
        allow_password_prompt=allow_password_prompt,
    )
    if not ok:
        return False, f"could not reassign public objects to {ROLE_MIGRATE}: {detail}"

    if _migrate_can_enable_rls_on_diagrams(migrate_url):
        return True, f"Reassigned public objects to {ROLE_MIGRATE}"
    return False, (
        f"{ROLE_MIGRATE} still cannot ENABLE ROW LEVEL SECURITY on diagrams after REASSIGN"
    )


def _migrate_role_lacks_bypassrls(connect_url: str) -> bool:
    """True when mindgraph_migrate exists but does not have BYPASSRLS yet."""
    engine = create_engine(normalise_db_url(connect_url), poolclass=NullPool)
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT COALESCE(rolbypassrls, false) FROM pg_roles "
                    "WHERE rolname = 'mindgraph_migrate'"
                )
            ).scalar()
        if row is None:
            return False
        return row is False
    except Exception as exc:
        logger.debug("Could not read mindgraph_migrate rolbypassrls: %s", exc)
        return False
    finally:
        engine.dispose()


def ensure_migrate_role_bypassrls(
    base_url: str,
    *,
    allow_password_prompt: bool = True,
) -> tuple[bool, str]:
    """Grant BYPASSRLS via sudo when the migrate role exists without it."""
    if not _migrate_role_lacks_bypassrls(base_url):
        return True, f"{ROLE_MIGRATE} already has BYPASSRLS"
    runtime = normalise_db_url(_runtime_url())
    dbname = make_url(runtime).database or "mindgraph"
    ok, detail = _run_sudo_postgres_psql(
        dbname,
        build_ensure_migrate_bypassrls_sql(),
        allow_password_prompt=allow_password_prompt,
    )
    if not ok:
        return False, f"could not set BYPASSRLS on {ROLE_MIGRATE}: {detail}"
    return True, f"Set BYPASSRLS on {ROLE_MIGRATE}"


def _roles_missing_on_url(database_url: str) -> bool:
    engine = create_engine(normalise_db_url(database_url), poolclass=NullPool)
    try:
        return not (
            _role_exists(engine, ROLE_APP) and _role_exists(engine, ROLE_MIGRATE)
        )
    finally:
        engine.dispose()


def _verify_roles_created(base_url: str) -> bool:
    for role in (ROLE_APP, ROLE_MIGRATE):
        role_url = build_role_url(base_url, role)
        engine = create_engine(role_url, poolclass=NullPool)
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception as exc:
            logger.debug("Role login check failed for %s: %s", role, exc)
            return False
        finally:
            engine.dispose()
    return True


def _run_sudo_postgres_psql(
    dbname: str,
    sql: str,
    *,
    allow_password_prompt: bool,
) -> tuple[bool, str]:
    """
    Run ``sudo -u postgres psql -f …`` using a world-readable script under ``/tmp``.

    ``NamedTemporaryFile`` defaults to mode 0600, which the ``postgres`` OS user cannot
    read — that caused "Permission denied" on WSL.  Mode 0644 avoids that.
    """
    if sys.platform == "win32":
        return False, "sudo postgres bootstrap unavailable on Windows"

    sql_path = f"/tmp/mindgraph_rls_bootstrap_{os.getpid()}.sql"
    try:
        with open(sql_path, "w", encoding="utf-8") as handle:
            handle.write(sql)
        os.chmod(sql_path, 0o644)

        psql_args = [
            "psql",
            "-d",
            dbname,
            "-v",
            "ON_ERROR_STOP=1",
            "-f",
            sql_path,
        ]
        attempts: list[tuple[list[str], bool]] = [
            (["sudo", "-n", "-u", "postgres", *psql_args], True),
        ]
        if allow_password_prompt:
            attempts.append((["sudo", "-u", "postgres", *psql_args], False))

        last_detail = ""
        for cmd, capture in attempts:
            try:
                if capture:
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=120,
                        check=False,
                    )
                    last_detail = (result.stderr or result.stdout or "").strip()
                else:
                    print("[RLS] If prompted, enter your Linux password for sudo …")
                    result = subprocess.run(cmd, timeout=300, check=False)
                    last_detail = f"exit code {result.returncode}"
            except (OSError, subprocess.TimeoutExpired) as exc:
                last_detail = str(exc)
                continue
            if result.returncode == 0:
                return True, ""
            if not capture and result.returncode != 0:
                last_detail = f"exit code {result.returncode}"

        return False, last_detail or "sudo postgres psql failed"
    finally:
        try:
            os.unlink(sql_path)
        except OSError:
            pass


def try_bootstrap_rls_roles_via_sudo(
    runtime_url: str | None = None,
    *,
    allow_password_prompt: bool = True,
) -> tuple[bool, str]:
    """Create roles using ``sudo -u postgres psql`` (WSL/Linux dev default)."""
    runtime = normalise_db_url(runtime_url or _runtime_url())
    parsed = make_url(runtime)
    dbname = parsed.database or "mindgraph"
    sql = (
        build_create_roles_sql(_app_password(), _migrate_password())
        + "\n"
        + build_grants_sql()
        + "\n"
        + build_migrate_database_privileges_sql()
        + "\n"
        + build_reassign_public_objects_to_migrate_sql()
        + "\n"
        + build_ensure_postgresql_extensions_sql()
    )
    ok, detail = _run_sudo_postgres_psql(
        dbname,
        sql,
        allow_password_prompt=allow_password_prompt,
    )

    if not ok:
        hint = " (enter your Linux password when sudo prompts)" if allow_password_prompt else ""
        return False, f"sudo postgres psql failed: {detail}{hint}"

    base = first_connectable_database_url(runtime_url)
    if base is None:
        return True, "Created RLS roles via sudo -u postgres psql"
    if _verify_roles_created(base[0]):
        return True, "Created RLS roles via sudo -u postgres psql"
    return False, "sudo postgres psql ran but mindgraph_app/mindgraph_migrate login still failed"


def try_bootstrap_rls_roles(runtime_url: str | None = None) -> tuple[bool, str]:
    """
    Connect as superuser and create RLS roles.

    Returns (success, message).
    """
    probe = first_connectable_database_url(runtime_url)
    if probe is None:
        return False, "No DATABASE_URL candidate could connect (start PostgreSQL first)"
    base_url, _label = probe

    if not _roles_missing_on_url(base_url):
        return True, "RLS roles already exist"

    sudo_ok, sudo_msg = try_bootstrap_rls_roles_via_sudo(base_url)
    if sudo_ok:
        return True, sudo_msg

    last_error = ""
    for admin_url in admin_url_candidates(base_url):
        label = make_url(admin_url).username or "admin"
        try:
            engine = create_engine(admin_url, poolclass=NullPool, pool_pre_ping=True)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            bootstrap_rls_roles_with_engine(engine)
            engine.dispose()
            if _verify_roles_created(base_url):
                return True, f"Created RLS roles using {label}"
            last_error = f"{label}: roles still missing after bootstrap"
        except Exception as exc:
            last_error = f"{label}: {exc}"
            logger.debug("Admin URL failed (%s): %s", admin_url, exc)

    hint = (
        "Enter your Linux password when sudo prompts, or set "
        "PG_ADMIN_URL=postgresql://postgres:PASSWORD@localhost:5432/postgres in .env"
    )
    return False, f"{sudo_msg}. {last_error}. {hint}"


def ensure_rls_roles_exist(runtime_url: str | None = None) -> tuple[bool, str]:
    """Ensure mindgraph_app / mindgraph_migrate exist before Alembic (one-shot prep)."""
    probe = first_connectable_database_url(runtime_url)
    if probe is None:
        return False, "No DATABASE_URL candidate could connect (start PostgreSQL first)"
    base_url, _source = probe

    if not _roles_missing_on_url(base_url):
        bypass_ok, bypass_msg = ensure_migrate_role_bypassrls(base_url)
        if not bypass_ok:
            logger.error("%s", bypass_msg)
            return False, bypass_msg
        priv_ok, priv_msg = ensure_migrate_database_privileges(base_url)
        if not priv_ok:
            logger.error("%s", priv_msg)
            return False, priv_msg
        ext_ok, ext_msg = ensure_postgresql_extensions(base_url)
        if not ext_ok:
            logger.error("%s", ext_msg)
            return False, ext_msg
        return True, "RLS roles already exist"

    ok, msg = try_bootstrap_rls_roles(base_url)
    if not ok:
        logger.error("%s", msg)
        return False, msg

    logger.info("%s", msg)
    bypass_ok, bypass_msg = ensure_migrate_role_bypassrls(base_url)
    if not bypass_ok:
        logger.error("%s", bypass_msg)
        return False, bypass_msg
    priv_ok, priv_msg = ensure_migrate_database_privileges(base_url)
    if not priv_ok:
        logger.error("%s", priv_msg)
        return False, priv_msg
    ext_ok, ext_msg = ensure_postgresql_extensions(base_url)
    if not ext_ok:
        logger.error("%s", ext_msg)
        return False, ext_msg
    return True, msg


def iter_bootstrap_guidance() -> Iterable[str]:
    yield "PYTHONPATH=. python scripts/db/run_migrations.py  → menu option 4 (full local setup)"
    yield "Or set PG_ADMIN_URL=postgresql://postgres:PASSWORD@localhost:5432/postgres"
