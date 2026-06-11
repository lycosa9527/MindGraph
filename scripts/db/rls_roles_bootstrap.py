"""Bootstrap mindgraph_app / mindgraph_migrate when rev 0043 skipped (no CREATEROLE)."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path
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


def _psql_tcp_host_port() -> tuple[str, str]:
    """Host/port for the MindGraph PostgreSQL instance (not distro default socket)."""
    runtime = normalise_db_url(_runtime_url())
    parsed = make_url(runtime)
    host = (parsed.host or "localhost").strip()
    if host in ("localhost", ""):
        host = "127.0.0.1"
    port = str(parsed.port or int(os.getenv("POSTGRESQL_PORT", "5432")))
    return host, port


def _managed_postgresql_socket_dir() -> Path | None:
    """Socket directory for app-managed postgres (``POSTGRESQL_DATA_DIR``/sockets)."""
    raw = os.getenv("POSTGRESQL_DATA_DIR", "").strip()
    if not raw:
        return None
    socket_dir = Path(raw).expanduser() / "sockets"
    return socket_dir if socket_dir.is_dir() else None


def _psql_peer_auth_args() -> list[list[str]]:
    """
    Unix-socket targets for ``sudo -u postgres psql`` (peer auth, no password).

    Used for distro PostgreSQL (systemd on Ubuntu/WSL). Must be tried before TCP
    ``-h 127.0.0.1``, which requires a ``postgres`` role password.
    """
    args: list[list[str]] = [[]]
    distro_socket = Path("/var/run/postgresql")
    if distro_socket.is_dir():
        distro_arg = ["-h", str(distro_socket.resolve())]
        if distro_arg not in args:
            args.append(distro_arg)
    return args


def _psql_tcp_connection_args() -> list[list[str]]:
    """
    TCP and app-managed socket targets (password or custom socket).

    MindGraph's managed subprocess listens on ``127.0.0.1:POSTGRESQL_PORT``; its
    socket lives under ``POSTGRESQL_DATA_DIR/sockets`` when set.
    """
    host, port = _psql_tcp_host_port()
    args: list[list[str]] = [["-h", host, "-p", port]]
    socket_dir = _managed_postgresql_socket_dir()
    if socket_dir is not None:
        args.append(["-h", str(socket_dir.resolve())])
    return args


def _psql_host_connection_args() -> list[list[str]]:
    """Peer socket first, then TCP (backward-compatible combined list)."""
    peer = _psql_peer_auth_args()
    tcp = _psql_tcp_connection_args()
    combined: list[list[str]] = []
    seen: set[tuple[str, ...]] = set()
    for item in peer + tcp:
        key = tuple(item)
        if key not in seen:
            seen.add(key)
            combined.append(item)
    return combined


def _admin_url_for_database(dbname: str) -> str | None:
    """First admin URL that connects, with database set to ``dbname``."""
    for admin_url in admin_url_candidates():
        target = make_url(admin_url).set(database=dbname)
        url = normalise_db_url(target.render_as_string(hide_password=False))
        engine = create_engine(url, poolclass=NullPool, pool_pre_ping=True)
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return url
        except Exception as exc:
            logger.debug("Admin connect failed for %s: %s", url, exc)
        finally:
            engine.dispose()
    return None


def _try_run_sql_via_admin(dbname: str, sql: str) -> tuple[bool, str]:
    """Run superuser SQL over TCP when PG_ADMIN_URL / postgres password works."""
    admin_url = _admin_url_for_database(dbname)
    if admin_url is None:
        return False, "no admin database URL"
    engine = create_engine(admin_url, poolclass=NullPool)
    try:
        with engine.connect() as conn:
            conn.execute(text(sql))
            conn.commit()
        return True, ""
    except Exception as exc:
        return False, str(exc)
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


def _valid_db_name(dbname: str) -> bool:
    return bool(dbname) and all(ch.isalnum() or ch == "_" for ch in dbname)


def _run_sudo_postgres_cmd(
    cmd_tail: list[str],
    *,
    allow_password_prompt: bool,
    peer_first: bool = True,
) -> tuple[bool, str]:
    """Run a postgres CLI command via sudo peer auth, then TCP fallbacks."""
    if sys.platform == "win32":
        return False, "sudo postgres bootstrap unavailable on Windows"

    host_lists = (
        _psql_peer_auth_args() + _psql_tcp_connection_args()
        if peer_first
        else _psql_tcp_connection_args()
    )
    wrapper_plans: list[tuple[list[str], bool, bool, list[list[str]]]] = [
        (["sudo", "-n", "-u", "postgres"], True, True, host_lists),
    ]
    if allow_password_prompt:
        wrapper_plans.append((["sudo", "-u", "postgres"], False, True, host_lists))

    last_detail = ""
    bin_name = cmd_tail[0]
    rest = cmd_tail[1:]
    for prefix, capture, needs_sudo_hint, host_arg_lists in wrapper_plans:
        for host_args in host_arg_lists:
            cmd = [*prefix, bin_name, *host_args, *rest]
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
                    if needs_sudo_hint:
                        print("[RLS] If prompted, enter your Linux password for sudo …")
                    result = subprocess.run(cmd, timeout=300, check=False)
                    last_detail = f"exit code {result.returncode}"
            except (OSError, subprocess.TimeoutExpired) as exc:
                last_detail = str(exc)
                continue
            if result.returncode == 0:
                stdout = ""
                if capture:
                    stdout = (result.stdout or "").strip()
                return True, stdout
            if "already exists" in last_detail.lower():
                return True, ""
    return False, last_detail or "postgres command failed"


def _ensure_application_database_exists(
    dbname: str,
    *,
    allow_password_prompt: bool = True,
) -> tuple[bool, str]:
    """Create the application database when missing (distro PostgreSQL / peer auth)."""
    if not _valid_db_name(dbname):
        return False, f"invalid database name: {dbname}"
    escaped = dbname.replace("'", "''")
    check_sql = f"SELECT 1 FROM pg_database WHERE datname = '{escaped}'"
    check_cmd = ["psql", "-d", "postgres", "-tAc", check_sql]
    ok, detail = _run_sudo_postgres_cmd(
        check_cmd,
        allow_password_prompt=allow_password_prompt,
        peer_first=True,
    )
    if ok and detail.strip() == "1":
        return True, ""

    ok, detail = _run_sudo_postgres_cmd(
        ["createdb", dbname],
        allow_password_prompt=allow_password_prompt,
        peer_first=True,
    )
    if ok:
        return True, ""
    if "already exists" in detail.lower():
        return True, ""
    return False, detail or f"could not create database {dbname}"


def _run_sudo_postgres_psql(
    dbname: str,
    sql: str,
    *,
    allow_password_prompt: bool,
) -> tuple[bool, str]:
    """
    Apply superuser SQL via admin URL, then ``psql`` on the app PostgreSQL instance.

    Uses ``-h`` / ``-p`` from ``DATABASE_URL`` (managed subprocess), not the distro
    default socket under ``/var/run/postgresql``.  Falls back to ``sudo -u postgres``
    when direct ``psql`` is not available.

    ``NamedTemporaryFile`` defaults to mode 0600, which the ``postgres`` OS user cannot
    read — that caused "Permission denied" on WSL.  Mode 0644 avoids that.
    """
    if sys.platform == "win32":
        return False, "sudo postgres bootstrap unavailable on Windows"

    admin_ok, admin_detail = _try_run_sql_via_admin(dbname, sql)
    if admin_ok:
        return True, ""

    sql_path = f"/tmp/mindgraph_rls_bootstrap_{os.getpid()}.sql"
    try:
        with open(sql_path, "w", encoding="utf-8") as handle:
            handle.write(sql)
        os.chmod(sql_path, 0o644)

        last_detail = admin_detail
        tcp_args = _psql_tcp_connection_args()
        peer_args = _psql_peer_auth_args()
        wrapper_plans: list[tuple[list[str], bool, bool, list[list[str]]]] = [
            ([], True, False, tcp_args),
            (["sudo", "-n", "-u", "postgres"], True, True, peer_args + tcp_args),
        ]
        if allow_password_prompt:
            wrapper_plans.append(
                (["sudo", "-u", "postgres"], False, True, peer_args + tcp_args)
            )

        for prefix, capture, needs_sudo_hint, host_arg_lists in wrapper_plans:
            for host_args in host_arg_lists:
                psql_core = [
                    "psql",
                    *host_args,
                    "-U",
                    "postgres",
                    "-d",
                    dbname,
                    "-v",
                    "ON_ERROR_STOP=1",
                    "-f",
                    sql_path,
                ]
                cmd = [*prefix, *psql_core]
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
                        if needs_sudo_hint:
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

        return False, last_detail or "postgres psql failed"
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
    db_ok, db_msg = _ensure_application_database_exists(
        dbname,
        allow_password_prompt=allow_password_prompt,
    )
    if not db_ok:
        return False, db_msg

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
    runtime = normalise_db_url(runtime_url or _runtime_url())
    probe = first_connectable_database_url(runtime_url)
    bootstrap_msg = "RLS roles already exist"

    if probe is None:
        sudo_ok, sudo_msg = try_bootstrap_rls_roles_via_sudo(runtime)
        if not sudo_ok:
            return False, (
                f"{sudo_msg}. On a fresh install create the database first: "
                "sudo -u postgres createdb mindgraph"
            )
        logger.info("%s", sudo_msg)
        bootstrap_msg = sudo_msg
        probe = first_connectable_database_url(runtime_url)
        if probe is None:
            return False, (
                "MindGraph roles were bootstrapped but login still failed. "
                "Check MINDGRAPH_APP_PASSWORD / MINDGRAPH_MIGRATE_PASSWORD in .env"
            )
        base_url, _source = probe
    else:
        base_url, _source = probe
        if _roles_missing_on_url(base_url):
            ok, msg = try_bootstrap_rls_roles(base_url)
            if not ok:
                logger.error("%s", msg)
                return False, msg
            logger.info("%s", msg)
            bootstrap_msg = msg
        else:
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
            return True, bootstrap_msg
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
    return True, bootstrap_msg


def iter_bootstrap_guidance() -> Iterable[str]:
    yield "PYTHONPATH=. python scripts/db/run_migrations.py  → menu option 4 (full local setup)"
    yield "Or set PG_ADMIN_URL=postgresql://postgres:PASSWORD@localhost:5432/postgres"
