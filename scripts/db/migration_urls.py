"""Resolve runtime vs migrate PostgreSQL URLs for RLS rollout (used by run_migrations.py)."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse, urlunparse

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.pool import NullPool

logger = logging.getLogger(__name__)

ROLE_APP = "mindgraph_app"
ROLE_MIGRATE = "mindgraph_migrate"
ROLE_LEGACY = "mindgraph_user"

RLS_HEAD_REVISION = "0049"

_DEFAULT_RUNTIME = "postgresql://mindgraph_user:mindgraph_password@localhost:5432/mindgraph"


def normalise_db_url(url: str) -> str:
    """Match config.database URL normalisation (psycopg3 scheme)."""
    for legacy in ("postgresql+psycopg2://", "postgresql://", "postgres://"):
        if url.startswith(legacy):
            return "postgresql+psycopg://" + url[len(legacy) :]
    return url


_DEFAULT_PASSWORD = "mindgraph_password"
_MASKED_PASSWORDS = frozenset({"", "****", "***"})


def _password_for_role(role: str, fallback: str) -> str:
    if fallback in _MASKED_PASSWORDS:
        fallback = _DEFAULT_PASSWORD
    if role == ROLE_MIGRATE:
        return (
            os.getenv("MINDGRAPH_MIGRATE_PASSWORD")
            or os.getenv("POSTGRESQL_PASSWORD")
            or fallback
            or _DEFAULT_PASSWORD
        )
    if role == ROLE_LEGACY:
        return os.getenv("POSTGRESQL_PASSWORD") or fallback or _DEFAULT_PASSWORD
    if role == ROLE_APP:
        return (
            os.getenv("MINDGRAPH_APP_PASSWORD")
            or os.getenv("POSTGRESQL_PASSWORD")
            or fallback
            or _DEFAULT_PASSWORD
        )
    return fallback or _DEFAULT_PASSWORD


def _role_url_string(base_url: str, role: str) -> str:
    parsed = make_url(base_url)
    password = _password_for_role(role, parsed.password or "")
    return parsed.set(username=role, password=password).render_as_string(hide_password=False)


def build_role_url(base_url: str, role: str) -> str:
    """Same host/db as base_url, different login role (driver-normalised)."""
    return normalise_db_url(_role_url_string(base_url, role))


def url_for_dotenv(url: str) -> str:
    """``.env`` uses plain ``postgresql://`` with the real password (not ``***``)."""
    parsed = make_url(url)
    plain = parsed.render_as_string(hide_password=False)
    return plain.replace("postgresql+psycopg://", "postgresql://")


def _migrate_capable_username(url: str) -> str:
    return make_url(url).username or ""


def _runtime_url() -> str:
    raw = os.getenv("DATABASE_URL")
    if not raw:
        return normalise_db_url(_DEFAULT_RUNTIME)
    return normalise_db_url(raw)


def _explicit_migration_url() -> str | None:
    raw = os.getenv("DATABASE_MIGRATION_URL")
    if not raw or not raw.strip():
        return None
    return normalise_db_url(raw.strip())


def migration_url_candidates(runtime_url: str) -> list[tuple[str, str]]:
    """
    Ordered URLs to try for DDL / bootstrap (role, label).

    Never prefer mindgraph_app for migrations when other roles are available.
    """
    runtime_user = make_url(runtime_url).username or ""
    candidates: list[tuple[str, str]] = []

    explicit = _explicit_migration_url()
    if explicit:
        explicit_user = _migrate_capable_username(explicit)
        if explicit_user == ROLE_APP:
            logger.warning(
                "DATABASE_MIGRATION_URL uses %s (no BYPASSRLS); trying migrate-capable roles instead",
                ROLE_APP,
            )
        else:
            candidates.append((explicit, "DATABASE_MIGRATION_URL"))

    migrate_url = build_role_url(runtime_url, ROLE_MIGRATE)
    if not any(url == migrate_url for url, _ in candidates):
        candidates.append((migrate_url, f"auto ({ROLE_MIGRATE})"))

    legacy_url = build_role_url(runtime_url, ROLE_LEGACY)
    if not any(url == legacy_url for url, _ in candidates):
        candidates.append((legacy_url, f"auto ({ROLE_LEGACY})"))

    admin = os.getenv("PG_ADMIN_URL", "").strip()
    if admin:
        admin_url = normalise_db_url(admin)
        if not any(url == admin_url for url, _ in candidates):
            candidates.append((admin_url, "PG_ADMIN_URL"))

    if runtime_user not in (ROLE_APP,):
        if not any(url == runtime_url for url, _ in candidates):
            candidates.append((runtime_url, "DATABASE_URL"))

    if runtime_user == ROLE_APP:
        return candidates

    if not candidates:
        candidates.append((runtime_url, "DATABASE_URL"))
    return candidates


def first_connectable_database_url(
    runtime_url: str | None = None,
) -> tuple[str, str] | None:
    """Return the first working URL from migration candidates, or None."""
    runtime = normalise_db_url(runtime_url or _runtime_url())
    for url, label in migration_url_candidates(runtime):
        try:
            with create_migration_engine(url).connect() as conn:
                conn.execute(text("SELECT 1"))
            return url, label
        except Exception as exc:
            logger.debug("Database URL candidate failed (%s): %s", label, exc)
    return None


def resolve_migration_database_url() -> tuple[str, str]:
    """Pick migrate-capable URL; return (url, human-readable source)."""
    connected = first_connectable_database_url()
    if connected is not None:
        return connected
    runtime = _runtime_url()
    candidates = migration_url_candidates(runtime)
    if candidates:
        return candidates[0][0], candidates[0][1]
    raise RuntimeError("No DATABASE_URL migration candidates configured")


def pick_postgresql_connect_url() -> str:
    """First migrate-capable URL for starting local PostgreSQL (no connect test)."""
    runtime = _runtime_url()
    for url, _label in migration_url_candidates(runtime):
        user = make_url(url).username or ""
        if user != ROLE_APP:
            return url
    candidates = migration_url_candidates(runtime)
    return candidates[0][0] if candidates else runtime


def bootstrap_rls_migration_from_env() -> None:
    """
    Best-effort ``DATABASE_MIGRATION_URL`` resolution for app / Celery startup.

    Safe to call after ``load_dotenv()``; no-op for non-PostgreSQL ``DATABASE_URL``.
    """
    db_url = os.getenv("DATABASE_URL", "")
    if not db_url.startswith("postgresql"):
        return
    try:
        configure_rls_migration_environment()
    except Exception as exc:
        logger.warning("Could not auto-configure DATABASE_MIGRATION_URL: %s", exc)


def configure_rls_migration_environment() -> dict[str, str]:
    """
    Set ``DATABASE_MIGRATION_URL`` before ``config.database`` is imported.

    Ensures Alembic uses a migrate-capable role even when ``DATABASE_URL`` is
    already ``mindgraph_app``.
    """
    runtime = _runtime_url()
    runtime_user = make_url(runtime).username or ""
    if _explicit_migration_url() is None and runtime_user == ROLE_APP:
        logger.warning(
            "DATABASE_MIGRATION_URL is unset while DATABASE_URL uses %s; "
            "resolving a migrate-capable role for Alembic",
            ROLE_APP,
        )
    migration_url, source = resolve_migration_database_url()
    os.environ["DATABASE_MIGRATION_URL"] = migration_url
    info = {
        "runtime_url": runtime,
        "migration_url": migration_url,
        "migration_source": source,
    }
    logger.info("Runtime DATABASE_URL: %s", _mask_url(runtime))
    logger.info("Alembic DATABASE_MIGRATION_URL: %s (%s)", _mask_url(migration_url), source)
    return info


def create_migration_engine(migration_url: str) -> Engine:
    """Dedicated engine for migration script checks (not the app pool)."""
    return create_engine(
        migration_url,
        poolclass=NullPool,
        pool_pre_ping=True,
    )


def _mask_url(url: str) -> str:
    try:
        parsed = urlparse(url)
        if not parsed.password:
            return url
        user = parsed.username or ""
        host = parsed.hostname or ""
        port = f":{parsed.port}" if parsed.port else ""
        netloc = f"{user}:****@{host}{port}"
        return urlunparse(parsed._replace(netloc=netloc))
    except (ValueError, TypeError, AttributeError):
        return url


def _role_exists(engine: Engine, role: str) -> bool:
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT 1 FROM pg_roles WHERE rolname = :role"),
            {"role": role},
        ).first()
    return row is not None


def _revision_number(revision: str) -> int:
    digits = "".join(ch for ch in revision if ch.isdigit())
    return int(digits) if digits else 0


def _current_alembic_revision(engine: Engine) -> str | None:
    with engine.connect() as conn:
        row = conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).first()
    if row is None:
        return None
    return str(row[0])


def verify_rls_migration_complete(engine: Engine) -> tuple[bool, list[str]]:
    """
    Confirm mandatory RLS rollout (rev 0043+ roles, 0044+ policies on diagrams).

    Returns (ok, human-readable issue lines).
    """
    issues: list[str] = []
    if engine.dialect.name != "postgresql":
        return True, issues

    revision = _current_alembic_revision(engine)
    if revision is None:
        issues.append("alembic_version is empty — migrations did not run")
    elif _revision_number(revision) < _revision_number(RLS_HEAD_REVISION):
        issues.append(
            f"Alembic at {revision}; expected {RLS_HEAD_REVISION} or newer for mandatory RLS"
        )

    if not _role_exists(engine, ROLE_APP):
        issues.append(
            f"PostgreSQL role {ROLE_APP} missing "
            "(run scripts/db/run_migrations.py option 3 to bootstrap)"
        )
    if not _role_exists(engine, ROLE_MIGRATE):
        issues.append(
            f"PostgreSQL role {ROLE_MIGRATE} missing "
            "(run scripts/db/run_migrations.py option 3 to bootstrap)"
        )

    with engine.connect() as conn:
        rls_row = conn.execute(
            text(
                """
                SELECT c.relrowsecurity
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public' AND c.relname = 'diagrams'
                """
            ),
        ).first()
        policy_count = conn.execute(
            text("SELECT COUNT(*) FROM pg_policies WHERE schemaname = 'public' AND tablename = 'diagrams'"),
        ).scalar()

    if rls_row is None:
        issues.append("Table public.diagrams not found")
    elif not rls_row[0]:
        issues.append("RLS not enabled on diagrams (expected after rev 0044+)")
    elif not policy_count:
        issues.append("No RLS policies on diagrams (expected after rev 0044+)")

    return len(issues) == 0, issues


def rls_env_database_lines(runtime_url: str, migration_engine: Engine) -> list[str]:
    """Unmasked ``KEY=value`` lines to write into ``.env`` after RLS migrations."""
    lines: list[str] = []
    if _role_exists(migration_engine, ROLE_APP):
        lines.append(f"DATABASE_URL={url_for_dotenv(build_role_url(runtime_url, ROLE_APP))}")
    if _role_exists(migration_engine, ROLE_MIGRATE):
        lines.append(
            f"DATABASE_MIGRATION_URL={url_for_dotenv(build_role_url(runtime_url, ROLE_MIGRATE))}"
        )
    return lines


def _read_env_keys_from_file(env_path: Path, keys: set[str]) -> dict[str, str]:
    """Parse selected keys from ``.env`` without mutating ``os.environ``."""
    values: dict[str, str] = {}
    if not env_path.is_file() or not keys:
        return values
    try:
        raw = env_path.read_text(encoding="utf-8")
    except OSError:
        return values
    for raw_line in raw.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        if key in keys:
            values[key] = val.strip().strip("'").strip('"')
    return values


def env_rls_database_urls_match(env_path: Path, migration_engine: Engine) -> bool:
    """True when ``.env`` already has the recommended RLS database URLs."""
    runtime = _runtime_url()
    expected_lines = rls_env_database_lines(runtime, migration_engine)
    if not expected_lines:
        return False
    expected: dict[str, str] = {}
    for env_line in expected_lines:
        key, _, value = env_line.partition("=")
        expected[key] = value
    actual = _read_env_keys_from_file(env_path, set(expected.keys()))
    return actual == expected


def runtime_database_role() -> str:
    return make_url(_runtime_url()).username or ""


def _replace_or_append_env_key(lines: list[str], key: str, value: str) -> list[str]:
    prefix = f"{key}="
    out: list[str] = []
    replaced = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#") or not stripped:
            out.append(line)
            continue
        if stripped.startswith(prefix):
            out.append(f"{key}={value}\n")
            replaced = True
            continue
        out.append(line)
    if not replaced:
        if out and not out[-1].endswith("\n"):
            out[-1] = out[-1] + "\n"
        out.append(f"{key}={value}\n")
    return out


def _insert_env_key_after(lines: list[str], after_key: str, key: str, value: str) -> list[str]:
    """Insert ``key=value`` immediately after ``after_key=...`` when ``key`` is new."""
    prefix = f"{key}="
    after_prefix = f"{after_key}="
    for line in lines:
        if line.strip().startswith(prefix):
            return _replace_or_append_env_key(lines, key, value)

    out: list[str] = []
    inserted = False
    for line in lines:
        out.append(line)
        if not inserted and line.strip().startswith(after_prefix):
            if not line.endswith("\n"):
                out[-1] = out[-1] + "\n"
            out.append(f"{key}={value}\n")
            inserted = True
    if not inserted:
        out = _replace_or_append_env_key(out, key, value)
    return out


def _apply_env_database_patches(lines: list[str], patches: dict[str, str]) -> list[str]:
    """Patch DATABASE_URL and place DATABASE_MIGRATION_URL on the next line."""
    if "DATABASE_URL" in patches:
        lines = _replace_or_append_env_key(lines, "DATABASE_URL", patches["DATABASE_URL"])
    if "DATABASE_MIGRATION_URL" in patches:
        lines = _insert_env_key_after(
            lines,
            "DATABASE_URL",
            "DATABASE_MIGRATION_URL",
            patches["DATABASE_MIGRATION_URL"],
        )
    for key, value in patches.items():
        if key in ("DATABASE_URL", "DATABASE_MIGRATION_URL"):
            continue
        lines = _replace_or_append_env_key(lines, key, value)
    return lines


def _read_env_keys_from_file(env_path: Path, keys: set[str]) -> dict[str, str]:
    """Parse selected keys from ``.env`` without mutating ``os.environ``."""
    values: dict[str, str] = {}
    if not env_path.is_file() or not keys:
        return values
    try:
        raw = env_path.read_text(encoding="utf-8")
    except OSError:
        return values
    for raw_line in raw.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        if key in keys:
            values[key] = val.strip().strip("'").strip('"')
    return values


def env_rls_database_urls_match(env_path: Path, migration_engine: Engine) -> bool:
    """True when ``.env`` already has the recommended RLS database URLs."""
    runtime = _runtime_url()
    expected_lines = rls_env_database_lines(runtime, migration_engine)
    if not expected_lines:
        return False
    expected: dict[str, str] = {}
    for env_line in expected_lines:
        key, _, value = env_line.partition("=")
        expected[key] = value
    actual = _read_env_keys_from_file(env_path, set(expected.keys()))
    return actual == expected


def runtime_database_role() -> str:
    return make_url(_runtime_url()).username or ""


def update_env_rls_database_urls(env_path: Path, migration_engine: Engine) -> bool:
    """Patch ``.env`` with ``DATABASE_URL`` / ``DATABASE_MIGRATION_URL`` for mandatory RLS."""
    runtime = _runtime_url()
    env_lines = rls_env_database_lines(runtime, migration_engine)
    if not env_lines:
        logger.warning("No RLS roles in database; skipping .env update")
        return False
    if not env_path.is_file():
        logger.warning("Env file not found: %s", env_path)
        return False

    try:
        raw = env_path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.error("Could not read %s: %s", env_path, exc)
        return False

    lines = raw.splitlines(keepends=True)
    if not lines:
        lines = ["\n"]

    patches: dict[str, str] = {}
    for env_line in env_lines:
        key, _, value = env_line.partition("=")
        patches[key] = value
    lines = _apply_env_database_patches(lines, patches)

    try:
        env_path.write_text("".join(lines), encoding="utf-8")
    except OSError as exc:
        logger.error("Could not write %s: %s", env_path, exc)
        return False

    logger.info("Updated %s with RLS database URLs", env_path.name)
    return True


def print_rls_post_migration_guidance(migration_engine: Engine, env_path: Path) -> None:
    """Remind operator to set runtime vs migrate URLs in .env after RLS revs."""
    runtime = _runtime_url()
    runtime_user = make_url(runtime).username or ""
    has_app = _role_exists(migration_engine, ROLE_APP)
    has_migrate = _role_exists(migration_engine, ROLE_MIGRATE)

    print()
    print("=" * 60)
    print("RLS roles / .env (mandatory for app runtime)")
    print("=" * 60)
    print("  (Passwords below are masked in this summary; .env patch uses real values.)")
    for line in rls_env_database_lines(runtime, migration_engine):
        key, _, value = line.partition("=")
        print(f"  {key}={_mask_url(value)}")
    if not has_app:
        print(f"  DATABASE_URL=... (keep {ROLE_LEGACY} until {ROLE_APP} exists)")
    if not has_migrate:
        print(f"  DATABASE_MIGRATION_URL=... (use {ROLE_LEGACY} or postgres until {ROLE_MIGRATE} exists)")
    if runtime_user == ROLE_APP and has_app:
        print("  Runtime URL already uses mindgraph_app — OK for python main.py")
    elif has_app and runtime_user != ROLE_APP:
        print(
            f"  DATABASE_URL user is {runtime_user!r}; app runtime should use {ROLE_APP!r}"
        )
    elif has_app:
        print(f"  Update {env_path.name}: set DATABASE_URL to mindgraph_app, then restart the app")
    print("  Next: optional Redis FLUSHDB (prompt follows) to clear stale user/org/diagram cache")
    print("=" * 60)


def iter_connect_urls_for_postgres() -> Iterable[str]:
    """URLs to pass to ensure_postgresql_running (deduped)."""
    seen: set[str] = set()
    for url, _ in migration_url_candidates(_runtime_url()):
        if url not in seen:
            seen.add(url)
            yield url
