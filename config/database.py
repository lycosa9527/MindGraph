"""
Database Configuration for MindGraph Authentication
Author: lycosa9527
Made by: MindSpring Team

SQLAlchemy database setup and session management.
"""

import os
import sys
import asyncio
from pathlib import Path
from sqlalchemy import create_engine, event, inspect
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import OperationalError
from models.auth import Base, Organization
from datetime import datetime
import logging

# Import all models to ensure they're registered with Base metadata
# This ensures UpdateNotification, UpdateNotificationDismissed, etc. are registered
# when the module loads, so Base.metadata has complete table definitions
try:
    from models.auth import (
        User, APIKey,
        UpdateNotification, UpdateNotificationDismissed, Captcha,
        SMSVerification
    )
except ImportError:
    pass  # Models may not all exist yet

# Import TokenUsage model so it's registered with Base
try:
    from models.token_usage import TokenUsage
except ImportError:
    # TokenUsage model may not exist yet - that's okay
    TokenUsage = None

logger = logging.getLogger(__name__)

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
    old_db = Path("mindgraph.db").resolve()
    new_db = (DATA_DIR / "mindgraph.db").resolve()
    
    # Check if main database files exist in both locations
    old_exists = old_db.exists()
    new_exists = new_db.exists()
    
    if old_exists and new_exists:
        # Check for WAL/SHM files too
        old_wal = Path("mindgraph.db-wal").exists()
        old_shm = Path("mindgraph.db-shm").exists()
        new_wal = (DATA_DIR / "mindgraph.db-wal").exists()
        new_shm = (DATA_DIR / "mindgraph.db-shm").exists()
        
        env_db_url = os.getenv("DATABASE_URL", "not set")
        
        error_msg = "\n" + "=" * 80 + "\n"
        error_msg += "CRITICAL DATABASE CONFIGURATION ERROR\n"
        error_msg += "=" * 80 + "\n\n"
        error_msg += "Database files detected in BOTH locations:\n"
        error_msg += f"  - Root directory: {old_db}\n"
        error_msg += f"  - Data folder:    {new_db}\n\n"
        
        if old_wal or old_shm:
            error_msg += "Root directory also contains WAL/SHM files (active database).\n"
        if new_wal or new_shm:
            error_msg += "Data folder also contains WAL/SHM files (active database).\n"
        error_msg += "\n"
        
        error_msg += "Current DATABASE_URL configuration: "
        if env_db_url == "not set":
            error_msg += "not set (will default to data/mindgraph.db)\n"
        else:
            error_msg += f"{env_db_url}\n"
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
    import shutil
    
    # Check if user has explicitly set DATABASE_URL
    env_db_url = os.getenv("DATABASE_URL")
    
    # If DATABASE_URL is set to the old default path, we should still migrate
    # If it's set to something else (custom path), don't migrate
    if env_db_url and env_db_url != "sqlite:///./mindgraph.db":
        # User has custom DATABASE_URL (not old default), don't auto-migrate
        return True
    
    old_db = Path("mindgraph.db").resolve()
    new_db = (DATA_DIR / "mindgraph.db").resolve()
    
    # Only migrate if old exists and new doesn't
    if old_db.exists() and not new_db.exists():
        try:
            logger.info("Detected database in old location, migrating to data/ folder...")
            
            # Ensure data directory exists
            new_db.parent.mkdir(parents=True, exist_ok=True)
            
            # Move main database file (this is the only critical file)
            shutil.move(str(old_db), str(new_db))
            logger.info(f"Migrated {old_db} -> {new_db}")
            
            # Move WAL/SHM files if they exist (defensive - should be empty if server stopped cleanly)
            # These are temporary files, but we move them to be safe in case of unclean shutdown
            for suffix in ["-wal", "-shm"]:
                old_file = Path(f"mindgraph.db{suffix}").resolve()
                new_file = (DATA_DIR / f"mindgraph.db{suffix}").resolve()
                if old_file.exists():
                    shutil.move(str(old_file), str(new_file))
                    logger.debug(f"Migrated {old_file.name} -> {new_file}")
            
            logger.info("Database migration completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to migrate database: {e}", exc_info=True)
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
migration_success = migrate_old_database_if_needed()

# Database URL from environment variable
# Default location: data/mindgraph.db (keeps root directory clean)
env_db_url = os.getenv("DATABASE_URL")
if not env_db_url:
    # Determine which database location to use
    old_db = Path("mindgraph.db")
    new_db = DATA_DIR / "mindgraph.db"
    
    # If new database exists (migration succeeded or already migrated), use it
    if new_db.exists():
        DATABASE_URL = "sqlite:///./data/mindgraph.db"
    # If migration failed but old DB still exists, fall back to old location
    elif not migration_success and old_db.exists():
        logger.warning("Using old database location due to migration failure")
        DATABASE_URL = "sqlite:///./mindgraph.db"
    # Default to new location (will create new database if needed)
    else:
        DATABASE_URL = "sqlite:///./data/mindgraph.db"
else:
    DATABASE_URL = env_db_url

# Create SQLAlchemy engine with proper pool configuration
# For SQLite: use check_same_thread=False
# For PostgreSQL/MySQL: configure connection pool for production workloads
if "sqlite" in DATABASE_URL:
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,  # Verify connections before using
        echo=False  # Set to True for SQL query logging
    )
    
    # Enable WAL mode for better concurrent write performance
    # WAL allows multiple readers and one writer simultaneously
    # Without WAL: Only one writer at a time (database-level lock)
    # With WAL: Better concurrency for high workload scenarios
    @event.listens_for(engine, "connect")
    def enable_wal_mode(dbapi_conn, connection_record):
        """
        Enable WAL mode for SQLite to improve concurrent write performance.
        
        Optimized for multi-worker deployments (4 workers):
        - Busy timeout: 150ms (allows queued writes to complete)
        - Application-level retry logic handles transient locks with exponential backoff
        - Total worst-case wait: ~740ms (still < 1 second)
        - Typical wait: 10-150ms (most locks clear quickly)
        - Old approach: up to 5 seconds → ~7x faster
        """
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=150")  # Optimized for 4 workers: 150ms
        cursor.close()
else:
    # Production database (PostgreSQL/MySQL) pool configuration
    # - pool_size: Base number of connections to maintain
    # - max_overflow: Additional connections allowed beyond pool_size
    # - pool_timeout: Seconds to wait for a connection before timeout
    # - pool_pre_ping: Check connection validity before using (handles stale connections)
    # - pool_recycle: Recycle connections after N seconds (prevents stale connections)
    engine = create_engine(
        DATABASE_URL,
        pool_size=10,        # Increased from default 5
        max_overflow=20,     # Increased from default 10 (total max: 30)
        pool_timeout=60,     # Increased from default 30 seconds
        pool_pre_ping=True,  # Test connection before using
        pool_recycle=1800,   # Recycle connections every 30 minutes
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
    # Import here to avoid circular dependency
    from utils.auth import load_invitation_codes
    
    # Ensure all models are imported and registered with Base
    # This is critical for Base.metadata to have complete table definitions
    try:
        from models.auth import (
            Organization, User, APIKey,
            UpdateNotification, UpdateNotificationDismissed, Captcha,
            SMSVerification
        )
    except ImportError:
        pass  # Some models may not exist yet
    
    try:
        from models.token_usage import TokenUsage
    except ImportError:
        pass  # TokenUsage may not exist yet
    
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
        logger.debug(f"Inspector check failed (assuming new database): {e}")
        existing_tables = set()
    
    # Get all tables that should exist from Base metadata
    expected_tables = set(Base.metadata.tables.keys())
    
    # Determine which tables need to be created
    missing_tables = expected_tables - existing_tables
    
    if missing_tables:
        logger.info(f"Creating {len(missing_tables)} missing table(s): {', '.join(sorted(missing_tables))}")
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
                logger.debug(f"Table creation conflict resolved (table exists): {e}")
                logger.info("Database tables verified (already exist)")
            else:
                # Re-raise genuine errors (syntax, permissions, corruption, etc.)
                # This ensures we don't silently ignore real database problems
                logger.error(f"Database initialization error: {e}")
                raise
    else:
        logger.info("All database tables already exist - skipping creation")
    
    # Step 2: Run automatic migrations (add missing columns)
    try:
        from utils.db_migration import run_migrations
        migration_success = run_migrations()
        if migration_success:
            logger.info("Database schema migration completed")
        else:
            logger.warning("Database schema migration encountered issues - check logs")
    except Exception as e:
        logger.error(f"Migration manager error: {e}", exc_info=True)
        # Continue anyway - migration failures shouldn't break startup
    
    # Seed organizations
    db = SessionLocal()
    try:
        # Check if organizations already exist
        if db.query(Organization).count() == 0:
            # Prefer seeding from .env INVITATION_CODES if provided
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
                logger.info(f"Seeding organizations from .env: {len(seeded_orgs)} entries")
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
                logger.info(f"Seeded {len(seeded_orgs)} organizations")
        else:
            logger.info("Organizations already exist, skipping seed")
            
    except Exception as e:
        logger.error(f"Error seeding database: {e}")
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
        from sqlalchemy import text
        with engine.connect() as conn:
            # PRAGMA wal_checkpoint(TRUNCATE) - merges WAL pages and truncates WAL file
            # TRUNCATE mode: More aggressive - waits for all readers/writers to finish
            # This is safe for periodic checkpointing and shutdown
            result = conn.execute(text("PRAGMA wal_checkpoint(TRUNCATE)"))
            # Checkpoint returns: (busy, log, checkpointed)
            # busy=0 means checkpoint completed, busy=1 means there were active readers/writers
            checkpoint_result = result.fetchone()
            if checkpoint_result:
                busy, log_pages, checkpointed_pages = checkpoint_result[0], checkpoint_result[1], checkpoint_result[2]
                if busy == 0:
                    logger.debug(f"[Database] WAL checkpoint completed: {checkpointed_pages} pages checkpointed, {log_pages} pages remaining")
                else:
                    logger.debug(f"[Database] WAL checkpoint busy: {checkpointed_pages} pages checkpointed, {log_pages} pages remaining (some readers/writers active)")
        return True
    except Exception as e:
        logger.warning(f"[Database] WAL checkpoint failed: {e}")
        return False


async def start_wal_checkpoint_scheduler(interval_minutes: int = 5):
    """
    Run periodic WAL checkpointing in background.
    
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
    
    interval_seconds = interval_minutes * 60
    logger.info(f"[Database] Starting WAL checkpoint scheduler (every {interval_minutes} min)")
    
    while True:
        try:
            await asyncio.sleep(interval_seconds)
            
            # Check if backup is in progress (coordination with backup system)
            try:
                from services.backup_scheduler import is_backup_in_progress
                if is_backup_in_progress():
                    logger.debug("[Database] Skipping WAL checkpoint - backup in progress")
                    continue
            except ImportError:
                # Backup scheduler not available, continue anyway
                pass
            
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
            logger.error(f"[Database] WAL checkpoint scheduler error: {e}", exc_info=True)
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
        import os
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
                logger.warning(f"[Database] Low disk space: {free_mb:.1f} MB available, {required_mb} MB required")
                return False
            return True
        except AttributeError:
            # Windows doesn't have statvfs, skip check
            return True
    except Exception as e:
        logger.warning(f"[Database] Disk space check failed: {e}")
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
        import os
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
        
        from sqlalchemy import text
        with engine.connect() as conn:
            result = conn.execute(text("PRAGMA integrity_check"))
            row = result.fetchone()
        
        if row and row[0] == "ok":
            return True
        else:
            logger.error(f"[Database] Integrity check failed: {row}")
            return False
    except Exception as e:
        logger.error(f"[Database] Integrity check error: {e}")
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
