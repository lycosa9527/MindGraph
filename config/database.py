"""
Database Configuration for MindGraph Authentication
Author: lycosa9527
Made by: MindSpring Team

SQLAlchemy database setup and session management.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from datetime import datetime
from pathlib import Path
from typing import Optional
import asyncio
import logging
import os
import shutil
import sys
import time
import uuid

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

# Optional imports for Redis-based distributed locking
# These are imported at module level to avoid import-outside-toplevel warnings
# They're wrapped in try/except since Redis may not be available
try:
    from services.redis.redis_client import get_redis, is_redis_available
except ImportError:
    get_redis = None
    is_redis_available = None

# Optional import for backup scheduler coordination
# Imported at module level to avoid import-outside-toplevel warnings
try:
    from services.utils.backup_scheduler import is_backup_in_progress
except ImportError:
    is_backup_in_progress = None

# Optional import for invitation codes (lazy import to avoid circular dependency)
# Imported at module level to avoid import-outside-toplevel warnings
try:
    from utils.auth.invitations import load_invitation_codes
except ImportError:
    load_invitation_codes = None

# Import migration utility (auth import is lazy to avoid circular dependency)
from utils.db_migration import run_migrations
from models.auth import (
    Base, Organization, User, APIKey,
    UpdateNotification, UpdateNotificationDismissed
)
from models.token_usage import TokenUsage

logger = logging.getLogger(__name__)

# Import knowledge_space models to ensure they're registered with Base.metadata for migrations
# This MUST happen before run_migrations() is called
try:
    from models.knowledge_space import (
        ChunkTestDocument, ChunkTestDocumentChunk, ChunkTestResult,
        KnowledgeSpace, KnowledgeDocument, DocumentChunk
    )
    # Verify models are registered by accessing their tables
    _ = ChunkTestDocument.__tablename__
    _ = ChunkTestDocumentChunk.__tablename__
    _ = ChunkTestResult.__tablename__
    _ = KnowledgeSpace.__tablename__
    _ = KnowledgeDocument.__tablename__
    _ = DocumentChunk.__tablename__
    logger.debug("[Database] Knowledge space models imported and registered for migrations")
except ImportError as e:
    # Knowledge space models may not be available in all environments
    logger.warning("[Database] Could not import knowledge space models: %s", e)
except Exception as e:
    logger.warning("[Database] Error registering knowledge space models: %s", e)

# ============================================================================
# DISTRIBUTED LOCK FOR MULTI-WORKER COORDINATION (WAL Checkpoint)
# ============================================================================
#
# Problem: Uvicorn does NOT set UVICORN_WORKER_ID automatically.
# All workers get default '0', causing all to run WAL checkpoint schedulers.
#
# Solution: Redis-based distributed lock ensures only ONE worker checkpoints WAL.
# Uses SETNX (SET if Not eXists) with TTL for crash safety.
#
# Key: database:wal_checkpoint:lock
# Value: {worker_pid}:{uuid} (unique identifier per worker)
# TTL: 10 minutes (auto-release if worker crashes)
# ============================================================================

WAL_CHECKPOINT_LOCK_KEY = "database:wal_checkpoint:lock"
WAL_CHECKPOINT_LOCK_TTL = 600  # 10 minutes - auto-release if worker crashes


class WalCheckpointLockManager:
    """Manages WAL checkpoint lock ID for this worker to avoid global statement."""
    _lock_id: Optional[str] = None

    @staticmethod
    def _generate_lock_id() -> str:
        """Generate unique lock ID for this worker: {pid}:{uuid}"""
        return f"{os.getpid()}:{uuid.uuid4().hex[:8]}"

    @classmethod
    def get_lock_id(cls) -> str:
        """Get or generate lock ID for this worker."""
        if cls._lock_id is None:
            cls._lock_id = cls._generate_lock_id()
        return cls._lock_id

    @classmethod
    def has_lock_id(cls) -> bool:
        """Check if lock ID has been generated."""
        return cls._lock_id is not None


def acquire_wal_checkpoint_lock() -> bool:
    """
    Attempt to acquire the WAL checkpoint lock.

    Uses Redis SETNX for atomic lock acquisition.
    Only ONE worker across all processes can hold this lock.

    Returns:
        True if lock acquired (this worker should checkpoint WAL)
        False if lock held by another worker
    """
    if get_redis is None or is_redis_available is None:
        # Redis not available, assume single worker mode
        return True

    if not is_redis_available():
        # No Redis = single worker mode, proceed
        logger.debug("[Database] Redis unavailable, assuming single worker mode for WAL checkpoint")
        return True

    redis = get_redis()
    if not redis:
        return True  # Fallback to single worker mode

    try:
        # Generate unique ID for this worker
        lock_id = WalCheckpointLockManager.get_lock_id()

        # Attempt atomic lock acquisition: SETNX with TTL
        # Returns True only if key did not exist (lock acquired)
        acquired = redis.set(
            WAL_CHECKPOINT_LOCK_KEY,
            lock_id,
            nx=True,  # Only set if not exists
            ex=WAL_CHECKPOINT_LOCK_TTL  # TTL in seconds
        )

        if acquired:
            logger.debug(
                "[Database] WAL checkpoint lock acquired by this worker (id=%s)",
                lock_id
            )
            return True
        else:
            # Lock held by another worker - check who
            holder = redis.get(WAL_CHECKPOINT_LOCK_KEY)
            logger.debug(
                "[Database] Another worker holds the WAL checkpoint lock "
                "(holder=%s), this worker will not checkpoint WAL",
                holder
            )
            return False

    except Exception as e:
        logger.warning(
            "[Database] WAL checkpoint lock acquisition failed: %s, proceeding anyway",
            e
        )
        return True  # On error, proceed (better to have duplicate than no checkpoint)


def refresh_wal_checkpoint_lock() -> bool:
    """
    Refresh the WAL checkpoint lock TTL if held by this worker.

    Uses atomic Lua script to check-and-refresh in one operation,
    preventing race conditions where lock could be lost between check and refresh.

    Returns:
        True if lock refreshed, False if not held by this worker
    """
    if get_redis is None or is_redis_available is None:
        return False

    if not is_redis_available() or not WalCheckpointLockManager.has_lock_id():
        return False

    redis = get_redis()
    if not redis:
        return False

    try:
        lock_id = WalCheckpointLockManager.get_lock_id()
        # Atomic check-and-refresh using Lua script
        # Only refreshes TTL if current holder matches our ID
        lua_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            redis.call("expire", KEYS[1], ARGV[2])
            return 1
        else
            return 0
        end
        """
        result = redis.eval(lua_script, 1, WAL_CHECKPOINT_LOCK_KEY, lock_id, WAL_CHECKPOINT_LOCK_TTL)

        if result == 1:
            return True
        else:
            # Lock not held by us - check who holds it
            holder = redis.get(WAL_CHECKPOINT_LOCK_KEY)  # type: ignore[call-arg]
            logger.debug(
                "[Database] WAL checkpoint lock lost! Holder: %s, our ID: %s",
                holder,
                lock_id
            )
            return False

    except Exception as e:
        logger.debug("[Database] WAL checkpoint lock refresh failed: %s", e)
        return False


# Ensure data directory exists for database files
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)


def check_database_location_conflict():
    """
    Safety check: Detect if database files exist in both root and data folder.

    This is a critical check to prevent data confusion. If both locations have
    database files, the application will refuse to start and require manual resolution.

    Raises:
        SystemExit: If database files exist in both locations, with clear error message
    """
    old_db_path_conflict = Path("mindgraph.db").resolve()
    new_db_path_conflict = (DATA_DIR / "mindgraph.db").resolve()

    # Check if main database files exist in both locations
    old_exists = old_db_path_conflict.exists()
    new_exists = new_db_path_conflict.exists()

    if old_exists and new_exists:
        # Check for WAL/SHM files too
        old_wal = Path("mindgraph.db-wal").exists()
        old_shm = Path("mindgraph.db-shm").exists()
        new_wal = (DATA_DIR / "mindgraph.db-wal").exists()
        new_shm = (DATA_DIR / "mindgraph.db-shm").exists()

        db_url_env_conflict = os.getenv("DATABASE_URL", "not set")

        error_msg = "\n" + "=" * 80 + "\n"
        error_msg += "CRITICAL DATABASE CONFIGURATION ERROR\n"
        error_msg += "=" * 80 + "\n\n"
        error_msg += "Database files detected in BOTH locations:\n"
        error_msg += f"  - Root directory: {old_db_path_conflict}\n"
        error_msg += f"  - Data folder:    {new_db_path_conflict}\n\n"

        if old_wal or old_shm:
            error_msg += "Root directory also contains WAL/SHM files (active database).\n"
        if new_wal or new_shm:
            error_msg += "Data folder also contains WAL/SHM files (active database).\n"
        error_msg += "\n"

        error_msg += "Current DATABASE_URL configuration: "
        if db_url_env_conflict == "not set":
            error_msg += "not set (will default to data/mindgraph.db)\n"
        else:
            error_msg += f"{db_url_env_conflict}\n"
        error_msg += "\n"

        error_msg += "This situation can cause data confusion and potential data loss.\n"
        error_msg += "The application cannot start until this is resolved.\n\n"
        error_msg += "RESOLUTION STEPS:\n"
        error_msg += "1. Determine which database contains your actual data\n"
        error_msg += "2. Update DATABASE_URL in .env file to point to the correct location:\n"
        error_msg += "   - For root database: DATABASE_URL=sqlite:///./mindgraph.db\n"
        error_msg += "   - For data folder:  DATABASE_URL=sqlite:///./data/mindgraph.db\n"
        error_msg += "3. Delete database files from the OTHER location:\n"
        error_msg += "   - If using root: delete data/mindgraph.db* files\n"
        error_msg += "   - If using data folder: delete mindgraph.db* files from root\n"
        error_msg += "4. Restart the application\n\n"
        error_msg += "NOTE: The recommended location is data/mindgraph.db (keeps root clean).\n"
        error_msg += "=" * 80 + "\n"

        logger.critical(error_msg)
        print(error_msg, file=sys.stderr)
        raise SystemExit(1)


def migrate_old_database_if_needed():
    """
    Automatically migrate database from old location (root) to new location (data/).

    This handles the transition from mindgraph.db in root to data/mindgraph.db.
    Moves the main database file and any associated WAL/SHM files if they exist.

    Note: WAL/SHM files are temporary and should be empty/absent if server was
    stopped cleanly. We move them defensively in case of unclean shutdown.

    Returns:
        bool: True if migration succeeded or wasn't needed, False if migration failed
    """
    # Check if user has explicitly set DATABASE_URL
    db_url_env = os.getenv("DATABASE_URL")

    # If DATABASE_URL is set to the old default path, we should still migrate
    # If it's set to something else (custom path), don't migrate
    if db_url_env and db_url_env != "sqlite:///./mindgraph.db":
        # User has custom DATABASE_URL (not old default), don't auto-migrate
        return True

    old_db_path = Path("mindgraph.db").resolve()
    new_db_path = (DATA_DIR / "mindgraph.db").resolve()

    # Only migrate if old exists and new doesn't
    if old_db_path.exists() and not new_db_path.exists():
        try:
            logger.info("Detected database in old location, migrating to data/ folder...")

            # Ensure data directory exists
            new_db_path.parent.mkdir(parents=True, exist_ok=True)

            # Move main database file (this is the only critical file)
            shutil.move(str(old_db_path), str(new_db_path))
            logger.info("Migrated %s -> %s", old_db_path, new_db_path)

            # Move WAL/SHM files if they exist (defensive - should be empty if server stopped cleanly)
            # These are temporary files, but we move them to be safe in case of unclean shutdown
            for suffix in ["-wal", "-shm"]:
                old_file = Path(f"mindgraph.db{suffix}").resolve()
                new_file = (DATA_DIR / f"mindgraph.db{suffix}").resolve()
                if old_file.exists():
                    shutil.move(str(old_file), str(new_file))
                    logger.debug("Migrated %s -> %s", old_file.name, new_file)

            logger.info("Database migration completed successfully")
            return True

        except Exception as e:
            logger.error("Failed to migrate database: %s", e, exc_info=True)
            logger.error(
                "CRITICAL: Database migration failed. "
                "The old database remains in the root directory. "
                "Please migrate manually or fix the issue before starting the server."
            )
            return False

    return True


# CRITICAL SAFETY CHECK: Detect database files in both locations
# This must run BEFORE migration to catch the conflict early
check_database_location_conflict()

# Migrate old database location before creating engine
MIGRATION_SUCCESS = migrate_old_database_if_needed()

# Database URL from environment variable
# Default location: data/mindgraph.db (keeps root directory clean)
db_url_from_env = os.getenv("DATABASE_URL", None)
if not db_url_from_env:
    # Determine which database location to use
    old_db_path_check = Path("mindgraph.db")
    new_db_path_check = DATA_DIR / "mindgraph.db"

    # If new database exists (migration succeeded or already migrated), use it
    if new_db_path_check.exists():
        DATABASE_URL = "sqlite:///./data/mindgraph.db"
    # If migration failed but old DB still exists, fall back to old location
    elif not MIGRATION_SUCCESS and old_db_path_check.exists():
        logger.warning("Using old database location due to migration failure")
        DATABASE_URL = "sqlite:///./mindgraph.db"
    # Default to new location (will create new database if needed)
    else:
        DATABASE_URL = "sqlite:///./data/mindgraph.db"
else:
    DATABASE_URL = db_url_from_env

# Create SQLAlchemy engine with proper pool configuration
# For SQLite: use check_same_thread=False
# For PostgreSQL/MySQL: configure connection pool for production workloads
if "sqlite" in DATABASE_URL:
    # SQLite pool configuration for multi-worker deployments
    # Optimized for 500 concurrent registrations with safety margin:
    # - Base: 60 connections (handles normal load, increased from 50)
    # - Overflow: 120 connections (handles bursts, increased from 100)
    # - Total: 180 connections (enough for 500 concurrent registrations with headroom)
    # - Uses Redis distributed locks to prevent race conditions on phone uniqueness checks
    SQLITE_POOL_SIZE = int(os.getenv('DATABASE_POOL_SIZE', '60'))       # Base connections (increased from 50)
    SQLITE_MAX_OVERFLOW = int(os.getenv('DATABASE_MAX_OVERFLOW', '120'))  # Overflow connections (increased from 100)
    SQLITE_POOL_TIMEOUT = int(os.getenv('DATABASE_POOL_TIMEOUT', '30'))  # Wait time (seconds)

    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        pool_size=SQLITE_POOL_SIZE,        # Default: 10 (was 5)
        max_overflow=SQLITE_MAX_OVERFLOW,   # Default: 20 (was 10)
        pool_timeout=SQLITE_POOL_TIMEOUT,   # Default: 30 (was 30)
        pool_pre_ping=True,  # Verify connections before using
        echo=False  # Set to True for SQL query logging
    )

    # Enable WAL mode for better concurrent write performance
    # WAL allows multiple readers and one writer simultaneously
    # Without WAL: Only one writer at a time (database-level lock)
    # With WAL: Better concurrency for high workload scenarios
    @event.listens_for(engine, "connect")
    def enable_wal_mode(dbapi_conn, _connection_record):
        """
        Enable WAL mode for SQLite to improve concurrent write performance.

        Optimized for high concurrency (500 concurrent registrations):
        - Busy timeout: 1000ms (allows queued writes to complete, increased from 500ms)
        - Application-level retry logic handles transient locks with exponential backoff
        - Redis distributed locks prevent race conditions on phone uniqueness checks
        - Total worst-case wait: ~2s (with 5 retries)
        - Typical wait: 10-500ms (most locks clear quickly)
        - Connection pool: 60 base + 120 overflow = 180 total connections
        """
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=1000")  # Optimized for high concurrency: 1000ms (increased from 500ms)
        cursor.close()
else:
    # Production database (PostgreSQL/MySQL) pool configuration
    # - pool_size: Base number of connections to maintain
    # - max_overflow: Additional connections allowed beyond pool_size
    # - pool_timeout: Seconds to wait for a connection before timeout
    # - pool_pre_ping: Check connection validity before using (handles stale connections)
    # - pool_recycle: Recycle connections after N seconds (prevents stale connections)

    # Default pool configuration for 6 workers (configurable via environment variables)
    # Calculation: 6 workers × 5 base = 30, 6 workers × 10 overflow = 60
    DEFAULT_POOL_SIZE = 30        # Base connections (5 per worker for 6 workers)
    DEFAULT_MAX_OVERFLOW = 60      # Overflow connections (10 per worker for 6 workers)
    DEFAULT_POOL_TIMEOUT = 60     # Wait time for connection (seconds)

    # Allow environment variable overrides
    pool_size_str = os.getenv('DATABASE_POOL_SIZE', str(DEFAULT_POOL_SIZE))
    max_overflow_str = os.getenv('DATABASE_MAX_OVERFLOW', str(DEFAULT_MAX_OVERFLOW))
    pool_timeout_str = os.getenv('DATABASE_POOL_TIMEOUT', str(DEFAULT_POOL_TIMEOUT))
    pool_size = int(pool_size_str)
    max_overflow = int(max_overflow_str)
    pool_timeout = int(pool_timeout_str)

    engine = create_engine(
        DATABASE_URL,
        pool_size=pool_size,        # Default: 30 (for 6 workers), override via DATABASE_POOL_SIZE
        max_overflow=max_overflow,   # Default: 60 (for 6 workers), override via DATABASE_MAX_OVERFLOW
        pool_timeout=pool_timeout,  # Default: 60 seconds, override via DATABASE_POOL_TIMEOUT
        pool_pre_ping=True,          # Test connection before using
        pool_recycle=1800,           # Recycle connections every 30 minutes
        echo=False
    )

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """
    Initialize database: create tables, run migrations, and seed demo data.

    This function:
    1. Ensures all models are registered with Base metadata
    2. Creates missing tables using inspector to avoid conflicts
    3. Runs migrations to add missing columns
    4. Seeds initial data if needed
    """
    # Verify models are registered by checking Base.metadata contains their tables
    # This ensures models are loaded and registered before table creation
    # Accessing __tablename__ attributes ensures models are used, satisfying Pylint
    try:
        auth_model_tables = [
            Organization.__tablename__,
            User.__tablename__,
            APIKey.__tablename__,
            UpdateNotification.__tablename__,
            UpdateNotificationDismissed.__tablename__
        ]
        registered_tables = set(Base.metadata.tables.keys())
        missing_tables = set(auth_model_tables) - registered_tables
        if missing_tables:
            logger.warning(
                "Some auth models not registered: %s",
                missing_tables
            )
    except (ImportError, AttributeError):
        pass  # Some models may not exist yet or may not have __tablename__

    try:
        # Verify TokenUsage is registered by accessing __tablename__
        token_usage_table = TokenUsage.__tablename__
        if token_usage_table not in Base.metadata.tables:
            logger.warning(
                "TokenUsage model not registered with Base.metadata: %s",
                token_usage_table
            )
    except (ImportError, AttributeError):
        pass  # TokenUsage may not exist yet or may not have __tablename__

    # Step 1: Create missing tables (proactive approach)
    # SAFETY: This approach is safe for existing databases:
    # 1. Inspector check is read-only (doesn't modify database)
    # 2. create_all() with checkfirst=True checks existence before creating (SQLAlchemy's built-in safety)
    # 3. Error handling catches edge cases gracefully
    # 4. Only creates tables, never modifies or deletes existing tables or data
    try:
        inspector = inspect(engine)
        existing_tables = set(inspector.get_table_names())
    except Exception as e:
        # If inspector fails (e.g., database doesn't exist yet, connection issue),
        # assume no tables exist. This is safe because create_all() with checkfirst=True
        # will verify existence before creating, so no tables will be overwritten.
        logger.debug("Inspector check failed (assuming new database): %s", e)
        existing_tables = set()

    # Get all tables that should exist from Base metadata
    expected_tables = set(Base.metadata.tables.keys())

    # Determine which tables need to be created
    missing_tables = expected_tables - existing_tables

    if missing_tables:
        missing_tables_sorted = ', '.join(sorted(missing_tables))
        logger.info(
            "Creating %d missing table(s): %s",
            len(missing_tables),
            missing_tables_sorted
        )
        try:
            # Create missing tables
            # SAFETY: checkfirst=True (default) ensures SQLAlchemy checks if each table exists
            # before attempting to create it. This prevents "table already exists" errors
            # and ensures we never overwrite existing tables or data.
            Base.metadata.create_all(bind=engine, checkfirst=True)
            logger.info("Database tables created/verified")
        except OperationalError as e:
            # Fallback: Handle edge cases where inspector and SQLAlchemy disagree
            # This can happen if table was created between inspector check and create_all call
            # SAFETY: We only catch "already exists" errors - genuine errors are re-raised
            error_msg = str(e).lower()
            if "already exists" in error_msg or ("table" in error_msg and "exists" in error_msg):
                logger.debug("Table creation conflict resolved (table exists): %s", e)
                logger.info("Database tables verified (already exist)")
            else:
                # Re-raise genuine errors (syntax, permissions, corruption, etc.)
                # This ensures we don't silently ignore real database problems
                logger.error("Database initialization error: %s", e)
                # Send critical alert for database errors during initialization
                try:
                    from services.infrastructure.monitoring.critical_alert import CriticalAlertService
                    error_msg_lower = str(e).lower()
                    if "corrupt" in error_msg_lower or "integrity" in error_msg_lower:
                        CriticalAlertService.send_startup_failure_alert_sync(
                            component="Database",
                            error_message=f"Database error during initialization: {str(e)}",
                            details="Database may be corrupted or have integrity issues. Check database file and permissions."
                        )
                except Exception as alert_error:  # pylint: disable=broad-except
                    logger.error("Failed to send database error alert: %s", alert_error)
                raise
    else:
        logger.info("All database tables already exist - skipping creation")

    # Step 2: Run automatic migrations (add missing columns)
    try:
        migration_result = run_migrations()
        if migration_result:
            logger.info("Database schema migration completed")
        else:
            logger.warning("Database schema migration encountered issues - check logs")
    except Exception as e:
        logger.error("Migration manager error: %s", e, exc_info=True)
        # Continue anyway - migration failures shouldn't break startup

    # Seed organizations
    db = SessionLocal()
    try:
        # Check if organizations already exist
        if db.query(Organization).count() == 0:
            # Prefer seeding from .env INVITATION_CODES if provided
            env_codes = None
            if load_invitation_codes is not None:
                env_codes = load_invitation_codes()
            seeded_orgs = []
            if env_codes:
                for org_code, (invite, _expiry) in env_codes.items():
                    # Use org_code as name fallback; admin can edit later
                    seeded_orgs.append(
                        Organization(
                            code=org_code,
                            name=org_code,
                            invitation_code=invite,
                            created_at=datetime.utcnow()
                        )
                    )
                logger.info("Seeding organizations from .env: %d entries", len(seeded_orgs))
            else:
                # Fallback demo data if .env not configured
                # Format: AAAA-XXXXX (4 uppercase letters, dash, 5 uppercase letters/digits)
                seeded_orgs = [
                    Organization(
                        code="DEMO-001",
                        name="Demo School for Testing",
                        invitation_code="DEMO-A1B2C",
                        created_at=datetime.utcnow()
                    ),
                    Organization(
                        code="SPRING-EDU",
                        name="Springfield Elementary School",
                        invitation_code="SPRN-9K2L1",
                        created_at=datetime.utcnow()
                    ),
                    Organization(
                        code="BJ-001",
                        name="Beijing First High School",
                        invitation_code="BJXX-M3N4P",
                        created_at=datetime.utcnow()
                    ),
                    Organization(
                        code="SH-042",
                        name="Shanghai International School",
                        invitation_code="SHXX-Q5R6S",
                        created_at=datetime.utcnow()
                    )
                ]
                logger.info("Seeding default demo organizations (no INVITATION_CODES in .env)")

            if seeded_orgs:
                db.add_all(seeded_orgs)
                db.commit()
                logger.info("Seeded %d organizations", len(seeded_orgs))
        else:
            logger.info("Organizations already exist, skipping seed")

    except Exception as e:
        logger.error("Error seeding database: %s", e)
        db.rollback()
    finally:
        db.close()


def get_db():
    """
    Dependency function to get database session

    Usage in FastAPI:
        @router.get("/users")
        async def get_users(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def checkpoint_wal():
    """
    Checkpoint WAL file to merge changes into main database.
    This prevents WAL file from growing indefinitely and reduces corruption risk.

    Returns:
        bool: True if checkpoint succeeded, False otherwise
    """
    if "sqlite" not in DATABASE_URL:
        return True  # Not SQLite, no checkpoint needed

    try:
        with engine.connect() as conn:
            # PRAGMA wal_checkpoint(TRUNCATE) - merges WAL pages and truncates WAL file
            # TRUNCATE mode: More aggressive - waits for all readers/writers to finish
            # This is safe for periodic checkpointing and shutdown
            result = conn.execute(text("PRAGMA wal_checkpoint(TRUNCATE)"))
            # Checkpoint returns: (busy, log, checkpointed)
            # busy=0 means checkpoint completed, busy=1 means there were active readers/writers
            checkpoint_result = result.fetchone()
            if checkpoint_result:
                busy, log_pages, checkpointed_pages = (
                    checkpoint_result[0],
                    checkpoint_result[1],
                    checkpoint_result[2]
                )
                if busy == 0:
                    logger.debug(
                        "[Database] WAL checkpoint completed: %d pages checkpointed, "
                        "%d pages remaining",
                        checkpointed_pages,
                        log_pages
                    )
                else:
                    logger.debug(
                        "[Database] WAL checkpoint busy: %d pages checkpointed, "
                        "%d pages remaining (some readers/writers active)",
                        checkpointed_pages,
                        log_pages
                    )
        return True
    except Exception as e:
        logger.warning("[Database] WAL checkpoint failed: %s", e)
        return False


async def start_wal_checkpoint_scheduler(interval_minutes: int = 5):
    """
    Run periodic WAL checkpointing in background.

    Uses Redis distributed lock to ensure only ONE worker checkpoints WAL.
    This prevents multiple workers from checkpointing simultaneously, which could
    cause conflicts or unnecessary work.

    This is critical for database safety, especially when using kill -9 (SIGKILL)
    which bypasses graceful shutdown. Periodic checkpointing ensures:
    - WAL file doesn't grow too large
    - Changes are merged to main database regularly
    - Faster recovery if process is force-killed
    - Reduced corruption risk

    COORDINATION WITH BACKUP:
    - Checks if backup is in progress before checkpointing
    - If backup is running, skips checkpoint (backup API handles WAL correctly)
    - This is an optimization - backup API works fine even if checkpoint runs

    Args:
        interval_minutes: How often to checkpoint WAL (default: 5 minutes)
    """
    if "sqlite" not in DATABASE_URL:
        return  # Not SQLite, no checkpoint needed

    # Attempt to acquire distributed lock
    # Only ONE worker across all processes will succeed
    if not acquire_wal_checkpoint_lock():
        # Lock acquisition already logged the skip message
        # Keep running but don't do anything - just monitor
        # If the lock holder dies, this worker can try to acquire on next check
        # Check every 5 minutes (lock TTL is 10 minutes, so 5 min is safe)
        while True:
            try:
                await asyncio.sleep(300)  # Check every 5 minutes (reduced from 1 minute)
                if acquire_wal_checkpoint_lock():
                    logger.info("[Database] WAL checkpoint lock acquired, this worker will now checkpoint WAL")
                    break
            except asyncio.CancelledError:
                logger.info("[Database] WAL checkpoint scheduler monitor stopped")
                return
            except Exception:
                pass

    # This worker holds the lock - run the scheduler
    interval_seconds = interval_minutes * 60
    logger.info(
        "[Database] Starting WAL checkpoint scheduler (every %d min)",
        interval_minutes
    )

    while True:
        try:
            await asyncio.sleep(interval_seconds)

            # Refresh lock periodically to prevent expiration
            if not refresh_wal_checkpoint_lock():
                logger.warning("[Database] Lost WAL checkpoint lock, stopping scheduler on this worker")
                # Try to reacquire lock
                if not acquire_wal_checkpoint_lock():
                    continue  # Another worker has it, keep waiting

            # Check if backup is in progress (coordination with backup system)
            if is_backup_in_progress is not None and is_backup_in_progress():
                logger.debug("[Database] Skipping WAL checkpoint - backup in progress")
                continue

            # Run checkpoint in thread pool to avoid blocking event loop
            # checkpoint_wal() handles its own exceptions and returns False on failure
            success = await asyncio.to_thread(checkpoint_wal)
            if success:
                logger.debug("[Database] Periodic WAL checkpoint completed")
            else:
                logger.warning("[Database] Periodic WAL checkpoint failed (will retry at next interval)")
        except asyncio.CancelledError:
            logger.info("[Database] WAL checkpoint scheduler stopped")
            break
        except Exception as e:
            # This catches unexpected errors (e.g., from asyncio.to_thread or asyncio.sleep)
            logger.error("[Database] WAL checkpoint scheduler error: %s", e, exc_info=True)
            # Wait shorter time before retrying after unexpected errors
            # This ensures we don't wait too long if there's a transient issue
            await asyncio.sleep(60)  # Wait 1 minute before retrying


def check_disk_space(required_mb: int = 100) -> bool:
    """
    Check if there's enough disk space for database operations.

    Args:
        required_mb: Minimum required disk space in MB

    Returns:
        bool: True if enough space available, False otherwise
    """
    try:
        # Extract file path from SQLite URL (same logic as recovery script)
        db_url = DATABASE_URL
        if db_url.startswith("sqlite:////"):
            # Absolute path (4 slashes: sqlite:////absolute/path)
            db_path = Path(db_url.replace("sqlite:////", "/"))
        elif db_url.startswith("sqlite:///"):
            # Relative path (3 slashes: sqlite:///./path or sqlite:///path)
            db_path_str = db_url.replace("sqlite:///", "")
            if db_path_str.startswith("./"):
                db_path_str = db_path_str[2:]  # Remove "./"
            if not os.path.isabs(db_path_str):
                db_path = Path.cwd() / db_path_str
            else:
                db_path = Path(db_path_str)
        else:
            # Fallback
            db_path = Path(db_url.replace("sqlite:///", ""))

        # Try to get disk space (Unix/Linux)
        try:
            stat = os.statvfs(db_path.parent)
            free_mb = (stat.f_bavail * stat.f_frsize) / (1024 * 1024)
            if free_mb < required_mb:
                logger.warning(
                    "[Database] Low disk space: %.1f MB available, %d MB required",
                    free_mb,
                    required_mb
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
    Check database integrity using SQLite integrity_check.

    Returns:
        bool: True if database is healthy, False if corrupted
    """
    if "sqlite" not in DATABASE_URL:
        return True  # Not SQLite, skip check

    try:
        # Check if database file exists first
        db_url = DATABASE_URL
        if db_url.startswith("sqlite:////"):
            db_path = Path(db_url.replace("sqlite:////", "/"))
        elif db_url.startswith("sqlite:///"):
            db_path_str = db_url.replace("sqlite:///", "")
            if db_path_str.startswith("./"):
                db_path_str = db_path_str[2:]
            if not os.path.isabs(db_path_str):
                db_path = Path.cwd() / db_path_str
            else:
                db_path = Path(db_path_str)
        else:
            db_path = Path(db_url.replace("sqlite:///", ""))

        # If database doesn't exist yet, it's fine (will be created)
        if not db_path.exists():
            return True

        with engine.connect() as conn:
            result = conn.execute(text("PRAGMA integrity_check"))
            row = result.fetchone()

        if row and row[0] == "ok":
            return True
        else:
            logger.error("[Database] Integrity check failed: %s", row)
            return False
    except Exception as e:
        logger.error("[Database] Integrity check error: %s", e)
        return False


def recover_from_kill_9():
    """
    Recover from kill -9 scenarios by cleaning up stale locks and connections.
    
    This function should be called on startup to handle cases where the process
    was killed with kill -9 (SIGKILL), which bypasses graceful shutdown.
    
    Handles:
    - SQLite WAL file locks from killed processes
    - Stale database connections in connection pool
    - Database file locks that may persist
    
    Returns:
        bool: True if recovery succeeded, False otherwise
    """
    if "sqlite" not in DATABASE_URL:
        return True  # Not SQLite, no recovery needed

    try:
        logger.info("[Database] Recovering from potential kill -9 scenario...")

        # First, dispose of any existing connections in the pool
        # This clears stale connections from previous process
        try:
            engine.dispose()
            logger.debug("[Database] Disposed existing connection pool")
        except Exception as e:
            logger.warning("[Database] Error disposing connection pool: %s", e)

        # Force checkpoint WAL to clear any locks
        # This is safe even if WAL is already checkpointed
        try:
            checkpoint_result = checkpoint_wal()
            if checkpoint_result:
                logger.debug("[Database] WAL checkpoint completed during recovery")
            else:
                logger.warning("[Database] WAL checkpoint failed during recovery")
        except Exception as e:
            logger.warning("[Database] Error during WAL checkpoint recovery: %s", e)

        # Try to open a new connection to verify database is accessible
        # This will fail if database is still locked
        try:
            with engine.connect() as conn:
                # Execute a simple query to verify database is accessible
                result = conn.execute(text("SELECT 1"))
                result.fetchone()
                logger.debug("[Database] Database connection verified after recovery")
        except Exception as e:
            logger.error(
                "[Database] Database still locked after recovery attempt: %s",
                e
            )
            # Try one more time with a short delay
            time.sleep(0.1)
            try:
                with engine.connect() as conn:
                    result = conn.execute(text("SELECT 1"))
                    result.fetchone()
                    logger.info("[Database] Database connection verified after retry")
            except Exception as retry_error:
                logger.error(
                    "[Database] Database recovery failed: %s",
                    retry_error
                )
                return False

        logger.info("[Database] Recovery from kill -9 scenario completed successfully")
        return True
        
    except Exception as e:
        logger.error(
            "[Database] Error during kill -9 recovery: %s",
            e,
            exc_info=True
        )
        return False


def close_db():
    """
    Close database connections (call on shutdown)
    """
    # Checkpoint WAL before closing
    if "sqlite" in DATABASE_URL:
        checkpoint_wal()

    engine.dispose()
    logger.info("Database connections closed")
