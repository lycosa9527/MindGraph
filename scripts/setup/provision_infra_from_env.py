#!/usr/bin/env python3
"""
Provision infrastructure to match MindGraph .env (PostgreSQL, Redis, Qdrant, Celery URLs).

Reads DATABASE_URL, REDIS_URL, QDRANT_HOST / QDRANT_URL, and Celery-related vars from
the project .env file, then:

  - Creates or updates PostgreSQL role + database when DATABASE_URL points at localhost
  - Ensures Redis responds at REDIS_URL (starts redis-server via systemd when local)
  - Installs/starts Qdrant when QDRANT_HOST / QDRANT_URL points at local 6333 (Linux + root)
  - Appends CELERY_BROKER_URL / CELERY_RESULT_BACKEND when missing so they match Redis

Usage (Ubuntu production, from repo root):

    sudo $(which python3) scripts/setup/provision_infra_from_env.py

Non-interactive. Requires sudo/root for PostgreSQL system user, Redis service, Qdrant install.

Copyright 2024-2025 Beijing Siyuan Zhijiao Technology Co., Ltd.
All Rights Reserved
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import platform
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Mapping, Optional

_PG_IDENT = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

# Module-level bindings for dynamic setup.py load (keeps importlib out of inner scope for linters)
_spec_from_file = importlib.util.spec_from_file_location
_module_from_spec = importlib.util.module_from_spec

# -----------------------------------------------------------------------------
# Project root + dotenv
# -----------------------------------------------------------------------------


def _resolve_project_root() -> Path:
    here = Path(__file__).resolve()
    for parent in [here.parent] + list(here.parents):
        if (parent / "requirements.txt").is_file():
            return parent
    return Path.cwd()


def _load_dotenv_manual(env_path: Path) -> dict[str, str]:
    """Minimal KEY=VALUE parser (no python-dotenv dependency for bootstrap)."""
    out: dict[str, str] = {}
    if not env_path.is_file():
        return out
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip("'").strip('"')
        out[key] = val
    return out


def _is_local_host(host: str) -> bool:
    h = (host or "").strip().lower()
    return h in ("localhost", "127.0.0.1", "::1", "")


def _run(
    cmd: list[str],
    *,
    check: bool = False,
    env: Optional[Mapping[str, str]] = None,
) -> subprocess.CompletedProcess[str]:
    run_env = {**os.environ, **dict(env)} if env else None
    return subprocess.run(
        cmd,
        check=check,
        capture_output=True,
        text=True,
        env=run_env,
    )


def _is_posix_root() -> bool:
    if os.name == "nt":
        return False
    try:
        return os.geteuid() == 0
    except AttributeError:
        return False


# -----------------------------------------------------------------------------
# DATABASE_URL → PostgreSQL
# -----------------------------------------------------------------------------


def _normalize_db_url(url: str) -> str:
    for legacy in ("postgresql+psycopg://", "postgresql+psycopg2://"):
        if url.startswith(legacy):
            return "postgresql://" + url[len(legacy) :]
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://") :]
    return url


def _parse_database_url(url: str) -> Optional[dict[str, Any]]:
    if not url or "sqlite" in url.lower():
        return None
    norm = _normalize_db_url(url)
    parsed = urllib.parse.urlparse(norm)
    if parsed.scheme not in ("postgresql",):
        return None
    db_path = (parsed.path or "").lstrip("/")
    if not db_path:
        return None
    user = urllib.parse.unquote(parsed.username or "")
    password = urllib.parse.unquote(parsed.password or "")
    host = parsed.hostname or "localhost"
    port = parsed.port or 5432
    return {
        "user": user,
        "password": password,
        "database": db_path.split("?")[0],
        "host": host,
        "port": port,
    }


def _pg_quote_literal(value: str) -> str:
    return value.replace("'", "''")


def _validate_pg_identifier(name: str, label: str) -> Optional[str]:
    if not _PG_IDENT.match(name):
        return (
            f"{label} {name!r} is not a safe PostgreSQL identifier (use letters, digits, underscore; see DATABASE_URL)"
        )
    return None


def _pg_sudo_sql(sql: str) -> tuple[bool, str]:
    result = _run(
        ["sudo", "-u", "postgres", "psql", "-v", "ON_ERROR_STOP=1", "-c", sql],
        check=False,
    )
    if result.returncode != 0:
        return False, (result.stderr or result.stdout or "psql failed").strip()
    return True, ""


def _postgres_connection_test(
    psql_bin: str,
    database_url: str,
    password: str,
) -> Optional[str]:
    norm = _normalize_db_url(database_url)
    ping = _run(
        [psql_bin, norm, "-c", "SELECT 1"],
        check=False,
        env={**os.environ, "PGPASSWORD": password},
    )
    if ping.returncode != 0:
        detail = (ping.stderr or ping.stdout or "").strip()
        return "PostgreSQL role/db created but connection test failed: " + detail
    return None


def _postgres_role_database_and_grants(
    user: str,
    password: str,
    database: str,
) -> Optional[str]:
    pw = _pg_quote_literal(password)
    role_sql = f"""
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{user}') THEN
    CREATE ROLE {user} WITH LOGIN PASSWORD '{pw}';
  ELSE
    ALTER ROLE {user} WITH PASSWORD '{pw}';
  END IF;
END
$$;
"""
    ok, err_msg = _pg_sudo_sql(role_sql)
    if not ok:
        return err_msg or "psql role failed"

    check_db = _run(
        [
            "sudo",
            "-u",
            "postgres",
            "psql",
            "-tAc",
            f"SELECT 1 FROM pg_database WHERE datname = '{database}'",
        ],
        check=False,
    )
    exists = (check_db.stdout or "").strip() == "1"
    if not exists:
        ok2, err2 = _pg_sudo_sql(f"CREATE DATABASE {database} OWNER {user};")
        if not ok2:
            return err2 or "CREATE DATABASE failed"

    ok3, err3 = _pg_sudo_sql(f"GRANT ALL PRIVILEGES ON DATABASE {database} TO {user};")
    if not ok3:
        return err3 or "GRANT DATABASE failed"

    grants_schema = (
        f"GRANT ALL ON SCHEMA public TO {user}; "
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO {user};"
    )
    result = _run(
        [
            "sudo",
            "-u",
            "postgres",
            "psql",
            "-v",
            "ON_ERROR_STOP=1",
            "-d",
            database,
            "-c",
            grants_schema,
        ],
        check=False,
    )
    if result.returncode != 0:
        return (result.stderr or result.stdout or "GRANT SCHEMA failed").strip()
    return None


def _postgres_apply_role_db_grants(
    user: str,
    password: str,
    database: str,
    database_url: str,
    psql_bin: str,
) -> tuple[bool, str]:
    err = _postgres_role_database_and_grants(user, password, database)
    if err:
        return False, err
    verify = _postgres_connection_test(psql_bin, database_url, password)
    if verify:
        return False, verify
    return True, "PostgreSQL user/database match DATABASE_URL"


def _provision_postgresql_local(cfg: dict[str, Any], database_url: str) -> tuple[bool, str]:
    user = cfg["user"]
    password = cfg["password"]
    database = cfg["database"]
    if not user or not database:
        return False, "DATABASE_URL missing user or database name"

    err = _validate_pg_identifier(user, "User")
    if err:
        return False, err
    err = _validate_pg_identifier(database, "Database")
    if err:
        return False, err

    psql = shutil.which("psql")
    if not psql:
        return False, "psql not found; install postgresql-client"

    return _postgres_apply_role_db_grants(user, password, database, database_url, psql)


# -----------------------------------------------------------------------------
# REDIS_URL
# -----------------------------------------------------------------------------


def _parse_redis_url(url: str) -> Optional[dict[str, Any]]:
    if not url or not url.startswith("redis"):
        return None
    parsed = urllib.parse.urlsplit(url.replace("rediss://", "redis://", 1))
    host = parsed.hostname or "localhost"
    port = parsed.port or 6379
    return {"host": host, "port": port, "raw": url}


def _redis_ping(url: str) -> bool:
    """Return True if redis-cli can PING the given redis:// or rediss:// URL."""
    cli = shutil.which("redis-cli")
    if not cli:
        return False
    r = _run([cli, "-u", url, "ping"], check=False)
    return r.returncode == 0 and (r.stdout or "").strip().upper() == "PONG"


def _provision_redis_local(redis_url: str, host: str, port: int) -> tuple[bool, str]:
    if _redis_ping(redis_url):
        return True, "Redis already accepts REDIS_URL"

    systemctl = shutil.which("systemctl")
    if systemctl and _is_local_host(host):
        for svc in ("redis-server", "redis"):
            st = _run([systemctl, "is-active", svc], check=False)
            if st.stdout and st.stdout.strip() == "active":
                break
            _run([systemctl, "start", svc], check=False)
        if _redis_ping(redis_url):
            return True, "Redis started via systemd"

    return False, (f"Redis did not respond to PING. Install/start Redis (see docs/REDIS_SETUP.md) for {host}:{port}")


# -----------------------------------------------------------------------------
# Qdrant (reuse setup.py installer on Linux)
# -----------------------------------------------------------------------------


def _parse_qdrant_endpoint(env: dict[str, str]) -> Optional[tuple[str, int]]:
    url = (env.get("QDRANT_URL") or "").strip()
    if url:
        parsed = urllib.parse.urlsplit(url)
        h = parsed.hostname or "localhost"
        p = parsed.port or 6333
        return h, p
    hostport = (env.get("QDRANT_HOST") or "").strip()
    if not hostport:
        return None
    if ":" in hostport:
        h, _, p = hostport.partition(":")
        return h.strip(), int(p.strip() or "6333")
    return hostport.strip(), 6333


def _qdrant_http_ok(host: str, port: int) -> bool:
    try:
        req = urllib.request.Request(f"http://{host}:{port}/", method="GET")
        with urllib.request.urlopen(req, timeout=3) as resp:
            return 200 <= resp.status < 500
    except (urllib.error.URLError, OSError, ValueError):
        return False


def _provision_qdrant_linux(project_root: Path) -> tuple[bool, str]:
    """
    Load scripts/setup/setup.py and run install_qdrant_via_documented_flow (Linux, root).

    Returns:
        Success flag and a short status message.
    """
    setup_py = project_root / "scripts" / "setup" / "setup.py"
    if not setup_py.is_file():
        return False, "scripts/setup/setup.py not found"

    spec = _spec_from_file("mindgraph_setup", setup_py)
    if spec is None or spec.loader is None:
        return False, "Could not load setup.py"
    mod = _module_from_spec(spec)
    spec.loader.exec_module(mod)
    ok = mod.install_qdrant_via_documented_flow(
        str(project_root),
        skip=False,
        allow_non_root=False,
    )
    if ok:
        return True, "Qdrant installed or already running"
    return False, "Qdrant install did not succeed (see docs/QDRANT_SETUP.md)"


# -----------------------------------------------------------------------------
# Celery env sync (broker = Redis, same host/port as REDIS_URL, DB from REDIS_CELERY_DB)
# -----------------------------------------------------------------------------


def _sync_celery_keys_in_dotenv(
    env_path: Path,
    redis_url: str,
    celery_db: str,
) -> tuple[bool, str]:
    """Append CELERY_BROKER_URL and CELERY_RESULT_BACKEND to .env when absent."""
    if not redis_url:
        return False, "REDIS_URL empty"

    parsed = urllib.parse.urlsplit(redis_url.replace("rediss://", "redis://", 1))
    host = parsed.hostname or "localhost"
    port = parsed.port or 6379
    password = parsed.password
    scheme = "rediss" if redis_url.startswith("rediss://") else "redis"

    if password:
        userinfo = f":{urllib.parse.quote(password, safe='')}@"
    else:
        userinfo = ""
    base = f"{scheme}://{userinfo}{host}:{port}/{celery_db}"

    text = env_path.read_text(encoding="utf-8") if env_path.is_file() else ""
    lines = text.splitlines()
    keys_present = any(line.strip().startswith("CELERY_BROKER_URL=") for line in lines)
    if keys_present:
        return True, "CELERY_BROKER_URL already in .env (not overwriting)"

    append = [
        "",
        "# --- Celery (auto-appended by provision_infra_from_env.py; broker matches Redis) ---",
        f"CELERY_BROKER_URL={base}",
        f"CELERY_RESULT_BACKEND={base}",
    ]
    with open(env_path, "a", encoding="utf-8") as handle:
        handle.write("\n".join(append) + "\n")
    os.environ["CELERY_BROKER_URL"] = base
    os.environ["CELERY_RESULT_BACKEND"] = base
    return (
        True,
        f"Appended CELERY_BROKER_URL / CELERY_RESULT_BACKEND ({base.split('@')[-1]})",
    )


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------


def _step_postgresql(
    args: argparse.Namespace,
    database_url: str,
    is_root: bool,
) -> int:
    pg_cfg = _parse_database_url(database_url)
    if args.skip_postgres or not pg_cfg or not _is_local_host(pg_cfg["host"]):
        if pg_cfg and not _is_local_host(pg_cfg["host"]):
            print(f"[INFO] DATABASE_URL host is remote ({pg_cfg['host']}); skipping local PostgreSQL create")
        return 0
    if args.dry_run:
        print(f"[DRY-RUN] Would provision PostgreSQL user={pg_cfg['user']} db={pg_cfg['database']}")
        return 0
    if not is_root:
        print(
            "[WARN] PostgreSQL provisioning needs sudo. Re-run: "
            "sudo $(which python3) scripts/setup/provision_infra_from_env.py"
        )
        return 0
    ok, msg = _provision_postgresql_local(pg_cfg, database_url)
    print(("[OK] " if ok else "[FAIL] ") + msg)
    return 0 if ok else 1


def _step_redis(
    args: argparse.Namespace,
    redis_url: str,
    is_root: bool,
) -> int:
    if args.skip_redis or not redis_url:
        return 0
    if args.dry_run:
        print("[DRY-RUN] Would check/start Redis for REDIS_URL")
        return 0
    if _redis_ping(redis_url):
        print("[OK] Redis responds to REDIS_URL")
        return 0
    rp = _parse_redis_url(redis_url)
    if not rp or not _is_local_host(rp["host"]):
        print("[WARN] Redis not reachable at REDIS_URL (remote host); fix network/firewall")
        return 0
    if not is_root:
        print(
            "[WARN] Could not ping Redis; start it with sudo or install Redis. "
            "Example: sudo systemctl start redis-server"
        )
        return 0
    ok, msg = _provision_redis_local(redis_url, rp["host"], rp["port"])
    print(("[OK] " if ok else "[FAIL] ") + msg)
    return 0


def _step_qdrant(
    args: argparse.Namespace,
    file_vars: dict[str, str],
    project_root: Path,
    is_root: bool,
) -> None:
    if args.skip_qdrant:
        return
    env_for_qdrant = {**file_vars, **dict(os.environ)}
    q_ep = _parse_qdrant_endpoint(env_for_qdrant)
    if not q_ep:
        return
    qh, qp = q_ep
    if not (_is_local_host(qh) and qp == 6333):
        print(f"[INFO] Qdrant endpoint {qh}:{qp} — local auto-install only supports localhost:6333; verify manually")
        return
    if args.dry_run:
        print("[DRY-RUN] Would ensure Qdrant on localhost:6333")
        return
    if _qdrant_http_ok(qh, qp):
        print("[OK] Qdrant HTTP responds")
        return
    if platform.system().lower() == "linux" and is_root:
        ok, msg = _provision_qdrant_linux(project_root)
        print(("[OK] " if ok else "[FAIL] ") + msg)
        return
    print("[WARN] Qdrant not reachable; run as root on Linux or install manually (docs/QDRANT_SETUP.md)")


def _step_celery_sync(
    args: argparse.Namespace,
    env_path: Path,
    redis_url: str,
    celery_db: str,
) -> None:
    if args.skip_celery_sync or not redis_url or not env_path.is_file():
        return
    if args.dry_run:
        print("[DRY-RUN] Would append CELERY_BROKER_URL / CELERY_RESULT_BACKEND if missing")
        return
    ok, msg = _sync_celery_keys_in_dotenv(env_path, redis_url, celery_db)
    print(("[OK] " if ok else "[INFO] ") + msg)


def main() -> int:
    """Load .env and provision local PostgreSQL, Redis, Qdrant; sync Celery broker URLs."""
    parser = argparse.ArgumentParser(description="Provision PostgreSQL, Redis, Qdrant, Celery env from .env")
    parser.add_argument(
        "--env-file",
        type=Path,
        default=None,
        help="Path to .env (default: <repo>/.env)",
    )
    parser.add_argument(
        "--skip-postgres",
        action="store_true",
        help="Skip PostgreSQL user/database creation",
    )
    parser.add_argument(
        "--skip-redis",
        action="store_true",
        help="Skip Redis check/start",
    )
    parser.add_argument(
        "--skip-qdrant",
        action="store_true",
        help="Skip Qdrant install/check",
    )
    parser.add_argument(
        "--skip-celery-sync",
        action="store_true",
        help="Do not append CELERY_BROKER_URL to .env",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print actions only (no writes, no sudo commands)",
    )
    args = parser.parse_args()

    project_root = _resolve_project_root()
    env_path = args.env_file or (project_root / ".env")
    file_vars = _load_dotenv_manual(env_path)

    for key, val in file_vars.items():
        if key not in os.environ:
            os.environ[key] = val

    is_root = _is_posix_root()

    print(f"[INFO] Project root: {project_root}")
    print(f"[INFO] Env file: {env_path} (exists={env_path.is_file()})")
    print(f"[INFO] Elevated (root): {is_root}")
    if args.dry_run:
        print("[INFO] Dry run — no changes will be made")

    database_url = os.environ.get("DATABASE_URL", file_vars.get("DATABASE_URL", ""))
    redis_url = os.environ.get("REDIS_URL", file_vars.get("REDIS_URL", ""))
    celery_db = os.environ.get("REDIS_CELERY_DB", file_vars.get("REDIS_CELERY_DB", "1"))

    code = _step_postgresql(args, database_url, is_root)
    if code != 0:
        return code
    _step_redis(args, redis_url, is_root)
    _step_qdrant(args, file_vars, project_root, is_root)
    _step_celery_sync(args, env_path, redis_url, celery_db)

    print("[INFO] Done. Next: pip install -r requirements.txt && python scripts/db/run_migrations.py && python main.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
