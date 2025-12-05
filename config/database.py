"""
Database Configuration for MindGraph Authentication
Author: lycosa9527
Made by: MindSpring Team

SQLAlchemy database setup and session management.
"""

import os
import sys
from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from models.auth import Base, Organization
from datetime import datetime
import logging

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
        """Enable WAL mode for SQLite to improve concurrent write performance"""
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")  # Wait up to 5 seconds for locks
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
    Initialize database: create tables, run migrations, and seed demo data
    """
    # Import here to avoid circular dependency
    from utils.auth import load_invitation_codes
    
    # Step 1: Create all tables (for new databases)
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created/verified")
    
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
                seeded_orgs = [
                    Organization(
                        code="DEMO-001",
                        name="Demo School for Testing",
                        invitation_code="DEMO2024",
                        created_at=datetime.utcnow()
                    ),
                    Organization(
                        code="SPRING-EDU",
                        name="Springfield Elementary School",
                        invitation_code="SPRING123",
                        created_at=datetime.utcnow()
                    ),
                    Organization(
                        code="BJ-001",
                        name="Beijing First High School",
                        invitation_code="BJ-INVITE",
                        created_at=datetime.utcnow()
                    ),
                    Organization(
                        code="SH-042",
                        name="Shanghai International School",
                        invitation_code="SH2024",
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


def close_db():
    """
    Close database connections (call on shutdown)
    """
    engine.dispose()
    logger.info("Database connections closed")

