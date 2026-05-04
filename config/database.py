"""
Database Configuration for MindGraph Authentication
Author: lycosa9527
Made by: MindSpring Team

SQLAlchemy database setup and session management.

Schema management is handled by Alembic (see ``alembic/`` and ``alembic.ini``).
On startup ``init_db()`` automatically applies any pending Alembic migrations
and then seeds initial data.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from datetime import UTC, datetime
from pathlib import Path
import logging
import os
import re
import time
import warnings

from sqlalchemy import create_engine, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker

from models.domain.registry import Base, Organization

try:
    from utils.auth.invitations import load_invitation_codes
except ImportError:
    load_invitation_codes = None

logger = logging.getLogger(__name__)

# Ensure data directory exists for database files
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)


# Database URL from environment variable.
# psycopg3 requires the scheme "postgresql+psycopg://".
# Transparently normalise legacy "postgresql://" and "postgresql+psycopg2://" values
# from existing .env files so no external config change is needed.
def _normalise_db_url(url: str) -> str:
    """Rewrite legacy psycopg2 URL schemes to the psycopg3 scheme."""
    for legacy in ("postgresql+psycopg2://", "postgresql://", "postgres://"):
        if url.startswith(legacy):
            return "postgresql+psycopg://" + url[len(legacy) :]
    return url


_LIBPQ_SCHEME = re.compile(r"^postgresql\+[^/]+://", re.IGNORECASE)


def libpq_database_url(db_url: str) -> str:
    """
    Convert a SQLAlchemy PostgreSQL URL to a libpq-compatible connection URI.

    Strips the +driver suffix (e.g. +psycopg) so pg_dump, pg_restore, and
    psycopg2 accept the string.
    """
    if not db_url:
        return db_url
    return _LIBPQ_SCHEME.sub("postgresql://", db_url, count=1)


_DEFAULT_DB_URL = "postgresql://mindgraph_user:mindgraph_password@localhost:5432/mindgraph"
_RAW_DB_URL = os.getenv("DATABASE_URL")
if _RAW_DB_URL is None:
    warnings.warn(
        "DATABASE_URL environment variable is not set. "
        "Falling back to the insecure default credentials. "
        "This MUST be explicitly configured before deploying to production.",
        stacklevel=2,
    )
    _RAW_DB_URL = _DEFAULT_DB_URL
DATABASE_URL = _normalise_db_url(_RAW_DB_URL)

# Create SQLAlchemy engine with proper pool configuration
# PostgreSQL/MySQL pool configuration for production workloads
# - pool_size: Base number of connections to maintain
# - max_overflow: Additional connections allowed beyond pool_size
# - pool_timeout: Seconds to wait for a connection before timeout
# - pool_pre_ping: Check connection validity before using (handles stale connections)
# - pool_recycle: Recycle connections after N seconds (prevents stale connections)

# Per-process pool sizing (each uvicorn worker / Celery process has its own
# pool). FastAPI handlers always use the async engine; the sync engine is
# kept small because it is only used by Alembic, the migration lock, Celery
# tasks, and a few legacy sync code paths.
#
# Total connections demanded per uvicorn worker = async_pool + async_overflow
# (+ sync_pool + sync_overflow if Celery shares the process).
# Size PostgreSQL ``max_connections`` accordingly — see docs/db-tuning.md.
DEFAULT_ASYNC_POOL_SIZE = 50
DEFAULT_ASYNC_MAX_OVERFLOW = 100
DEFAULT_SYNC_POOL_SIZE = 5
DEFAULT_SYNC_MAX_OVERFLOW = 10
DEFAULT_POOL_TIMEOUT = 60  # Wait time for a connection (seconds)

# Allow environment variable overrides. ``DATABASE_POOL_SIZE`` /
# ``DATABASE_MAX_OVERFLOW`` are kept as legacy aliases that govern the async
# pool (the dominant FastAPI workload).
async_pool_size = int(
    os.getenv("DATABASE_ASYNC_POOL_SIZE") or os.getenv("DATABASE_POOL_SIZE") or str(DEFAULT_ASYNC_POOL_SIZE)
)
async_max_overflow = int(
    os.getenv("DATABASE_ASYNC_MAX_OVERFLOW") or os.getenv("DATABASE_MAX_OVERFLOW") or str(DEFAULT_ASYNC_MAX_OVERFLOW)
)
sync_pool_size = int(os.getenv("DATABASE_SYNC_POOL_SIZE", str(DEFAULT_SYNC_POOL_SIZE)))
sync_max_overflow = int(os.getenv("DATABASE_SYNC_MAX_OVERFLOW", str(DEFAULT_SYNC_MAX_OVERFLOW)))
pool_timeout = int(os.getenv("DATABASE_POOL_TIMEOUT", str(DEFAULT_POOL_TIMEOUT)))

# Backwards-compatible aliases consumed by older modules / tests.
pool_size = async_pool_size
max_overflow = async_max_overflow

# ---------------------------------------------------------------------------
# Per-connection PostgreSQL safety settings (G1 from db-tuning audit).
#
# These guard the application against runaway queries and idle transactions
# that can pin connections forever and starve the pool.  Each value is an
# env override so operators can tune for different workloads (e.g. raise the
# statement timeout for analytics jobs).
#
# Setting any of these to ``0`` reproduces legacy unbounded behaviour.
# ---------------------------------------------------------------------------
DEFAULT_STATEMENT_TIMEOUT_MS = 60_000
DEFAULT_IDLE_IN_TXN_TIMEOUT_MS = 30_000
DEFAULT_CONNECT_TIMEOUT_S = 10

statement_timeout_ms = int(os.getenv("DATABASE_STATEMENT_TIMEOUT_MS", str(DEFAULT_STATEMENT_TIMEOUT_MS)))
idle_in_txn_timeout_ms = int(os.getenv("DATABASE_IDLE_IN_TXN_TIMEOUT_MS", str(DEFAULT_IDLE_IN_TXN_TIMEOUT_MS)))
connect_timeout_s = int(os.getenv("DATABASE_CONNECT_TIMEOUT_S", str(DEFAULT_CONNECT_TIMEOUT_S)))
application_name = os.getenv(
    "DATABASE_APPLICATION_NAME",
    f"mindgraph-w{os.getpid()}",
)


def _build_connect_args() -> dict:
    """Assemble psycopg3 connect_args from current environment settings.

    ``options`` is forwarded verbatim to libpq, which applies each ``-c key=val``
    pair on every new physical connection.  Zero-valued timeouts are omitted so
    operators can opt back into PostgreSQL's default unlimited behaviour.
    """
    options_parts: list[str] = []
    if statement_timeout_ms > 0:
        options_parts.append(f"-c statement_timeout={statement_timeout_ms}")
    if idle_in_txn_timeout_ms > 0:
        options_parts.append(f"-c idle_in_transaction_session_timeout={idle_in_txn_timeout_ms}")

    args: dict = {
        "application_name": application_name,
        "connect_timeout": connect_timeout_s,
    }
    if options_parts:
        args["options"] = " ".join(options_parts)
    return args


_CONNECT_ARGS = _build_connect_args()

# ``pool_use_lifo=True`` keeps the most recently used connection at the top
# of the pool (G5).  Under bursty traffic this lets idle connections close
# naturally via ``pool_recycle`` instead of getting refreshed in round-robin
# fashion, which is also friendlier to PgBouncer transaction pooling.
_POOL_USE_LIFO = os.getenv("DATABASE_POOL_USE_LIFO", "true").lower() == "true"

engine = create_engine(
    DATABASE_URL,
    pool_size=sync_pool_size,
    max_overflow=sync_max_overflow,
    pool_timeout=pool_timeout,
    pool_pre_ping=True,
    pool_recycle=1800,
    pool_use_lifo=_POOL_USE_LIFO,
    connect_args=_CONNECT_ARGS,
    echo=False,
)

# Sync session factory — ONLY for Celery tasks, migration scripts, and thread
# targets that cannot use async.  All FastAPI routes must use AsyncSessionLocal.
SyncSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
SessionLocal = SyncSessionLocal  # backward-compat alias (will be removed)

# ---------------------------------------------------------------------------
# Async engine & session factory  (native async via psycopg3)
# ---------------------------------------------------------------------------
_QUERY_CACHE_SIZE = int(os.getenv("DATABASE_QUERY_CACHE_SIZE", "1200"))


def _assert_pool_fits_max_connections() -> None:
    """
    Hard startup failure when pool demand exceeds max_connections.

    Enabled with ``DATABASE_POOL_HARD_ASSERT=1``.  The formula requires
    knowing the number of uvicorn workers, exposed by the ``WEB_CONCURRENCY``
    (or ``UVICORN_WORKERS``) env var; when absent the check is skipped.
    """
    if os.getenv("DATABASE_POOL_HARD_ASSERT", "0") not in ("1", "true", "True"):
        return
    raw_workers = (
        os.getenv("WEB_CONCURRENCY")
        or os.getenv("UVICORN_WORKERS")
    )
    if not raw_workers:
        return
    workers = int(raw_workers)
    demand = workers * (async_pool_size + async_max_overflow)
    max_conn = int(os.getenv("DATABASE_MAX_CONNECTIONS", "0"))
    if max_conn <= 0:
        return
    if demand > max_conn:
        raise RuntimeError(
            f"Connection pool overflow: {workers} workers × "
            f"({async_pool_size} pool + {async_max_overflow} overflow) = {demand} "
            f"exceeds DATABASE_MAX_CONNECTIONS={max_conn}. "
            f"Reduce pool sizes or raise max_connections before deploying."
        )


_assert_pool_fits_max_connections()

async_engine = create_async_engine(
    DATABASE_URL,
    pool_size=async_pool_size,
    max_overflow=async_max_overflow,
    pool_timeout=pool_timeout,
    pool_pre_ping=True,
    pool_recycle=1800,
    pool_use_lifo=_POOL_USE_LIFO,
    connect_args=_CONNECT_ARGS,
    echo=False,
    query_cache_size=_QUERY_CACHE_SIZE,
)

AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


def _seed_organizations_if_empty() -> None:
    """Insert organizations when the table is empty (INVITATION_CODES or demo defaults)."""
    db = SyncSessionLocal()
    try:
        org_count = db.execute(select(func.count()).select_from(Organization)).scalar_one()
        if org_count != 0:
            logger.info("Organizations already exist, skipping seed")
            return

        env_codes = None
        if load_invitation_codes is not None:
            env_codes = load_invitation_codes()
        seeded_orgs = []
        if env_codes:
            for org_code, (invite, _expiry) in env_codes.items():
                seeded_orgs.append(
                    Organization(
                        code=org_code,
                        name=org_code,
                        invitation_code=invite,
                        created_at=datetime.now(UTC),
                    )
                )
            logger.info("Seeding organizations from .env: %d entries", len(seeded_orgs))
        else:
            seeded_orgs = [
                Organization(
                    code="DEMO-001",
                    name="Demo School for Testing",
                    invitation_code="DEMO-A1B2C",
                    created_at=datetime.now(UTC),
                ),
                Organization(
                    code="SPRING-EDU",
                    name="Springfield Elementary School",
                    invitation_code="SPRN-9K2L1",
                    created_at=datetime.now(UTC),
                ),
                Organization(
                    code="BJ-001",
                    name="Beijing First High School",
                    invitation_code="BJXX-M3N4P",
                    created_at=datetime.now(UTC),
                ),
                Organization(
                    code="SH-042",
                    name="Shanghai International School",
                    invitation_code="SHXX-Q5R6S",
                    created_at=datetime.now(UTC),
                ),
            ]
            logger.info("Seeding default demo organizations (no INVITATION_CODES in .env)")

        if seeded_orgs:
            db.add_all(seeded_orgs)
            db.commit()
            logger.info("Seeded %d organizations", len(seeded_orgs))

    except Exception as e:
        logger.error("Error seeding database: %s", e)
        db.rollback()
    finally:
        db.close()


_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ALEMBIC_INI = str(_PROJECT_ROOT / "alembic.ini")
_ALEMBIC_SCRIPT_DIR = str(_PROJECT_ROOT / "alembic")
_MIGRATION_LOCK_KEY = "lock:mindgraph:alembic_migration"
# Baseline create_all can run far longer than two minutes; lock must outlive the migration.
_MIGRATION_LOCK_TTL = 3600
_MIGRATION_WAIT_INTERVAL_SEC = 2.0
_MIGRATION_WAIT_MAX_ATTEMPTS = 1800
_MIGRATION_LOCK_ID: "str | None" = None


def _get_alembic_version_num() -> str | None:
    """Return ``alembic_version.version_num`` or None if missing or unreadable.

    Uses plain SQL instead of Alembic's MigrationContext so workers that are
    waiting on a Redis migration lock do not emit Alembic INFO logs every poll
    (``Context impl PostgresqlImpl`` / ``Will assume transactional DDL``).
    """
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
            row = result.fetchone()
            return str(row[0]) if row else None
    except Exception:
        return None


def _run_alembic_upgrade() -> None:
    """Apply pending Alembic migrations if the DB is behind head.

    Compares the current ``alembic_version`` in the database to the latest
    revision on disk.  If they already match, this is a no-op.

    **Why a Redis lock:** every Uvicorn worker runs ``init_db()`` on startup
    (default ``UVICORN_WORKER_ID`` is ``0`` for all processes). Without a
    distributed lock, two workers could run ``alembic upgrade`` concurrently.

    **Waiting workers** poll ``alembic_version`` with plain SQL (not Alembic's
    ``MigrationContext``) so they do not emit Alembic INFO logs every second
    during long migrations.

    Workers that lose the lock wait until ``version_num`` matches head, then
    return without running DDL. If the peer never reaches head within the
    configured window, startup fails fast instead of continuing with a
    partial schema.
    """
    from alembic.command import upgrade as alembic_upgrade
    from alembic.config import Config as AlembicConfig
    from alembic.script import ScriptDirectory

    alembic_cfg = AlembicConfig(_ALEMBIC_INI)
    alembic_cfg.set_main_option("script_location", _ALEMBIC_SCRIPT_DIR)
    alembic_cfg.set_main_option("prepend_sys_path", str(_PROJECT_ROOT))
    script_dir = ScriptDirectory.from_config(alembic_cfg)
    head_rev = script_dir.get_current_head()

    current_rev = _get_alembic_version_num()

    if current_rev == head_rev:
        logger.info("[Database] Schema is up to date (revision %s)", current_rev)
        return

    if head_rev is None:
        logger.error(
            "[Database] Database has revision %s but no Alembic head revision found on disk.",
            current_rev,
        )
        raise RuntimeError("Alembic script directory has no head revision; cannot apply migrations or wait for a peer.")

    if current_rev is None:
        logger.info("[Database] No alembic_version found — running initial migration")
    else:
        logger.info(
            "[Database] Pending migration: %s → %s",
            current_rev,
            head_rev,
        )

    lock_acquired = False
    try:
        lock_acquired = _acquire_migration_lock()
        if not lock_acquired:
            _wait_for_migration_completion(head_rev)
            return
        alembic_upgrade(alembic_cfg, "head")
        logger.info("[Database] Alembic upgrade to head completed")
    finally:
        if lock_acquired:
            _release_migration_lock()


def _acquire_migration_lock() -> bool:
    """Try to acquire a Redis SETNX lock for migration exclusivity.

    Returns True if this process should run the migration, False if another
    worker already holds the lock.  Falls back to True (run anyway) when
    Redis is unavailable (single-worker or dev setup).
    """
    global _MIGRATION_LOCK_ID

    try:
        from services.redis.redis_client import get_redis, is_redis_available
    except ImportError:
        return True

    if not is_redis_available():
        return True

    redis = get_redis()
    if redis is None:
        return True

    lock_id = f"{os.getpid()}:{os.urandom(4).hex()}"
    acquired = redis.set(
        _MIGRATION_LOCK_KEY,
        lock_id,
        nx=True,
        ex=_MIGRATION_LOCK_TTL,
    )
    if acquired:
        _MIGRATION_LOCK_ID = lock_id
        logger.info("[Database] Migration lock acquired (id %s)", lock_id)
        return True

    logger.info("[Database] Migration lock held by another worker — waiting for completion")
    return False


def _release_migration_lock() -> None:
    """Release the Redis migration lock using compare-and-delete.

    Only deletes the key when its value matches the lock_id stored at
    acquisition time, so a worker that outlasts its own TTL cannot
    accidentally evict a lock legitimately held by a different worker.
    """
    global _MIGRATION_LOCK_ID

    if not _MIGRATION_LOCK_ID:
        return

    try:
        from services.redis.redis_client import RedisOps, is_redis_available
    except ImportError:
        _MIGRATION_LOCK_ID = None
        return

    if not is_redis_available():
        _MIGRATION_LOCK_ID = None
        return

    lock_id = _MIGRATION_LOCK_ID
    _MIGRATION_LOCK_ID = None

    try:
        RedisOps.compare_and_delete(_MIGRATION_LOCK_KEY, lock_id)
    except Exception as exc:
        logger.debug("[Database] Migration lock release (non-critical): %s", exc)


def _wait_for_migration_completion(expected_head: str) -> None:
    """Poll until the winner worker finishes the migration (revision matches head)."""
    for attempt in range(_MIGRATION_WAIT_MAX_ATTEMPTS):
        time.sleep(_MIGRATION_WAIT_INTERVAL_SEC)
        current = _get_alembic_version_num()
        if current == expected_head:
            logger.info(
                "[Database] Migration completed by another worker (revision %s)",
                current,
            )
            return
        if (attempt + 1) % 15 == 0:
            elapsed = int((attempt + 1) * _MIGRATION_WAIT_INTERVAL_SEC)
            logger.info(
                "[Database] Still waiting for migration to complete (~%d s elapsed, max ~%d s)...",
                elapsed,
                int(_MIGRATION_WAIT_MAX_ATTEMPTS * _MIGRATION_WAIT_INTERVAL_SEC),
            )

    logger.error(
        "[Database] Timed out waiting for peer worker to finish migrations "
        "(expected revision %s). Refusing to start with a possibly incomplete schema.",
        expected_head,
    )
    raise RuntimeError(
        "Timed out waiting for another worker to complete Alembic migrations. "
        "If first-time baseline migrations legitimately take longer than the "
        f"configured maximum (~{int(_MIGRATION_WAIT_MAX_ATTEMPTS * _MIGRATION_WAIT_INTERVAL_SEC)} s), "
        "increase _MIGRATION_WAIT_MAX_ATTEMPTS / _MIGRATION_WAIT_INTERVAL_SEC in config/database.py, "
        "or run `alembic upgrade head` once before starting multiple workers."
    )


def _check_pool_vs_max_connections() -> None:
    """Warn if configured pool exceeds PostgreSQL max_connections.

    Counts both the sync and async engines, plus a small reserve for
    Alembic / superuser sessions. The check is intentionally conservative:
    it warns when the *worst-case* concurrent demand crosses
    ``max_connections``.
    """
    workers = int(os.getenv("UVICORN_WORKERS", "1"))
    async_per_worker = async_pool_size + async_max_overflow
    sync_per_worker = sync_pool_size + sync_max_overflow
    per_worker = async_per_worker + sync_per_worker
    reserve = 10  # Alembic, ad-hoc psql, replication, ...
    total_needed = workers * per_worker + reserve
    try:
        with engine.connect() as conn:
            row = conn.execute(text("SHOW max_connections")).fetchone()
            if row is None:
                return
            pg_max = int(row[0])
    except Exception as exc:
        logger.debug("[Database] Could not query max_connections: %s", exc)
        return
    if total_needed > pg_max:
        logger.warning(
            "[Database] Pool config may exceed PostgreSQL capacity: "
            "%d workers × (async %d + sync %d = %d) + %d reserve = %d, "
            "but max_connections = %d. Risk of connection exhaustion — "
            "either lower DATABASE_*_POOL_SIZE / DATABASE_*_MAX_OVERFLOW, "
            "raise POSTGRESQL_MAX_CONNECTIONS, or front Postgres with PgBouncer.",
            workers,
            async_per_worker,
            sync_per_worker,
            per_worker,
            reserve,
            total_needed,
            pg_max,
        )
    else:
        logger.info(
            "[Database] Pool check OK: %d workers × (async %d + sync %d) + %d reserve = %d ≤ max_connections %d",
            workers,
            async_per_worker,
            sync_per_worker,
            reserve,
            total_needed,
            pg_max,
        )


def _ensure_pg_extensions() -> None:
    """Create observability extensions if they are missing.

    ``pg_stat_statements`` and ``auto_explain`` are loaded via
    ``shared_preload_libraries`` in the managed ``postgresql.conf`` template,
    but the extension itself still needs to be registered in each database
    so its views become queryable. This is idempotent and silent on
    permission errors (Aurora / managed Postgres often pre-installs them).
    """
    statements = (
        "CREATE EXTENSION IF NOT EXISTS pg_stat_statements",
        "CREATE EXTENSION IF NOT EXISTS pg_trgm",
    )
    for sql in statements:
        try:
            with engine.begin() as conn:
                conn.execute(text(sql))
        except Exception as exc:
            logger.debug(
                "[Database] Could not run %r (separate transaction; continuing): %s",
                sql,
                exc,
            )


def init_db(seed_organizations: bool = True):
    """
    Initialize the database: apply pending Alembic migrations, then seed data.

    On every startup this checks whether the PostgreSQL schema matches the
    latest Alembic revision.  If migrations are pending they are applied
    automatically.  If the schema is already current this is a fast no-op.

    Args:
        seed_organizations: When True (default), seed org rows if the table
            is empty.  Set False to skip seeding.
    """
    logger.debug(
        "[Database] %d table(s) registered on Base.metadata",
        len(Base.metadata.tables),
    )

    try:
        _run_alembic_upgrade()
    except Exception as exc:
        logger.error("[Database] Alembic migration failed: %s", exc, exc_info=True)
        raise

    _ensure_pg_extensions()
    _check_pool_vs_max_connections()

    if not seed_organizations:
        logger.info("Skipping organization seed (seed_organizations=False)")
        return

    _seed_organizations_if_empty()


def get_db_sync():
    """Sync dependency — only for Celery tasks and migration scripts."""
    db = SyncSessionLocal()
    try:
        yield db
    finally:
        db.close()


get_db = get_db_sync  # backward-compat alias (will be removed)


async def get_async_db():
    """Async dependency for FastAPI route handlers.

    Usage::

        @router.get("/users")
        async def get_users(db: AsyncSession = Depends(get_async_db)):
            result = await db.execute(select(User))
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


def check_disk_space(required_mb: int = 100) -> bool:
    """
    Check if there's enough disk space for database operations.

    Args:
        required_mb: Minimum required disk space in MB

    Returns:
        bool: True if enough space available, False otherwise
    """
    try:
        # Try to get disk space (Unix/Linux)
        try:
            # Use current working directory for disk space check
            stat = os.statvfs(Path.cwd())
            free_mb = (stat.f_bavail * stat.f_frsize) / (1024 * 1024)
            if free_mb < required_mb:
                logger.warning(
                    "[Database] Low disk space: %.1f MB available, %d MB required",
                    free_mb,
                    required_mb,
                )
                return False
            return True
        except AttributeError:
            # Windows doesn't have statvfs, skip check
            return True
    except Exception as e:
        logger.warning("[Database] Disk space check failed: %s", e)
        return True  # Assume OK if check fails


def check_integrity() -> bool:
    """
    Check database integrity using connection test.

    Returns:
        bool: True if database is healthy, False otherwise
    """
    try:
        with engine.connect() as conn:
            # Simple connection test
            result = conn.execute(text("SELECT 1"))
            result.fetchone()
        return True
    except Exception as e:
        logger.error("[Database] Integrity check error: %s", e)
        return False


async def check_integrity_async() -> bool:
    """Async variant of ``check_integrity`` using the async engine.

    Performs a lightweight ``SELECT 1`` against the async engine so health
    probes invoked from FastAPI endpoints never block the event loop.
    """
    try:
        async with async_engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            result.fetchone()
        return True
    except Exception as e:
        logger.error("[Database] Async integrity check error: %s", e)
        return False


def recover_from_kill_9():
    """
    Recover from kill -9 scenarios by cleaning up stale connections.

    This function should be called on startup to handle cases where the process
    was killed with kill -9 (SIGKILL), which bypasses graceful shutdown.

    Handles:
    - Stale database connections in connection pool

    Returns:
        bool: True if recovery succeeded, False otherwise
    """
    try:
        logger.debug("[Database] Recovering from potential kill -9 scenario...")

        # Dispose of any existing connections in the pool
        # This clears stale connections from previous process
        try:
            engine.dispose()
            logger.debug("[Database] Disposed existing connection pool")
        except Exception as e:
            logger.warning("[Database] Error disposing connection pool: %s", e)

        # Try to open a new connection to verify database is accessible
        try:
            with engine.connect() as conn:
                # Execute a simple query to verify database is accessible
                result = conn.execute(text("SELECT 1"))
                result.fetchone()
                logger.debug("[Database] Database connection verified after recovery")
        except Exception as e:
            logger.error("[Database] Database connection failed after recovery attempt: %s", e)
            # Try one more time with a short delay
            time.sleep(0.1)
            try:
                with engine.connect() as conn:
                    result = conn.execute(text("SELECT 1"))
                    result.fetchone()
                    logger.debug("[Database] Database connection verified after retry")
            except Exception as retry_error:
                logger.error("[Database] Database recovery failed: %s", retry_error)
                return False

        logger.debug("[Database] Recovery from kill -9 scenario completed successfully")
        return True

    except Exception as e:
        logger.error("[Database] Error during kill -9 recovery: %s", e, exc_info=True)
        return False


async def close_db():
    """Close both sync and async database connections (call on shutdown)."""
    engine.dispose()
    await async_engine.dispose()
    logger.info("Database connections closed")
