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
import logging
import os
import time

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import sessionmaker


# Optional import for invitation codes (lazy import to avoid circular dependency)
# Imported at module level to avoid import-outside-toplevel warnings
try:
    from utils.auth.invitations import load_invitation_codes
except ImportError:
    load_invitation_codes = None

# Optional import for critical alerts (lazy import to avoid circular dependency)
try:
    from services.infrastructure.monitoring.critical_alert import CriticalAlertService
except ImportError:
    CriticalAlertService = None

# Import migration utility (auth import is lazy to avoid circular dependency)
from utils.migration.postgresql.schema_migration import run_migrations
from models.domain.auth import (
    Base, Organization, User, APIKey,
    UpdateNotification, UpdateNotificationDismissed
)
from models.domain.token_usage import TokenUsage

logger = logging.getLogger(__name__)

# Import knowledge_space models to ensure they're registered with Base.metadata for migrations
# This MUST happen before run_migrations() is called
try:
    from models.domain.knowledge_space import (
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

# Import other models to ensure they're registered with Base.metadata for migrations
try:
    from models.domain.diagrams import Diagram
    _ = Diagram.__tablename__
    logger.debug("[Database] Diagram models imported and registered for migrations")
except ImportError as e:
    logger.debug("[Database] Could not import diagram models: %s", e)
except Exception as e:
    logger.debug("[Database] Error registering diagram models: %s", e)

try:
    from models.domain.debateverse import (
        DebateSession, DebateParticipant, DebateMessage, DebateJudgment
    )
    _ = DebateSession.__tablename__
    _ = DebateParticipant.__tablename__
    _ = DebateMessage.__tablename__
    _ = DebateJudgment.__tablename__
    logger.debug("[Database] Debate models imported and registered for migrations")
except ImportError as e:
    logger.debug("[Database] Could not import debate models: %s", e)
except Exception as e:
    logger.debug("[Database] Error registering debate models: %s", e)

try:
    from models.domain.school_zone import (
        SharedDiagram, SharedDiagramLike, SharedDiagramComment
    )
    _ = SharedDiagram.__tablename__
    _ = SharedDiagramLike.__tablename__
    _ = SharedDiagramComment.__tablename__
    logger.debug("[Database] School zone models imported and registered for migrations")
except ImportError as e:
    logger.debug("[Database] Could not import school zone models: %s", e)
except Exception as e:
    logger.debug("[Database] Error registering school zone models: %s", e)

try:
    from models.domain.pinned_conversations import PinnedConversation
    _ = PinnedConversation.__tablename__
    logger.debug("[Database] Pinned conversation models imported and registered for migrations")
except ImportError as e:
    logger.debug("[Database] Could not import pinned conversation models: %s", e)
except Exception as e:
    logger.debug("[Database] Error registering pinned conversation models: %s", e)

try:
    from models.domain.dashboard_activity import DashboardActivity
    _ = DashboardActivity.__tablename__
    logger.debug("[Database] Dashboard activity models imported and registered for migrations")
except ImportError as e:
    logger.debug("[Database] Could not import dashboard activity models: %s", e)
except Exception as e:
    logger.debug("[Database] Error registering dashboard activity models: %s", e)

try:
    from models.domain.user_activity_log import UserActivityLog
    from models.domain.user_usage_stats import UserUsageStats
    from models.domain.teacher_usage_config import TeacherUsageConfig
    _ = UserActivityLog.__tablename__
    _ = UserUsageStats.__tablename__
    _ = TeacherUsageConfig.__tablename__
    logger.debug("[Database] User activity/usage stats/config models imported and registered")
except ImportError as e:
    logger.debug("[Database] Could not import user activity/usage stats models: %s", e)
except Exception as e:
    logger.debug("[Database] Error registering user activity/usage stats models: %s", e)

try:
    from models.domain.library import (
        LibraryDocument, LibraryDanmaku, LibraryDanmakuLike, LibraryDanmakuReply,
        LibraryBookmark
    )
    _ = LibraryDocument.__tablename__
    _ = LibraryDanmaku.__tablename__
    _ = LibraryDanmakuLike.__tablename__
    _ = LibraryDanmakuReply.__tablename__
    _ = LibraryBookmark.__tablename__
    logger.debug("[Database] Library models imported and registered for migrations")
    logger.debug(
        "[Database] LibraryBookmark table name: %s, registered: %s",
        LibraryBookmark.__tablename__,
        LibraryBookmark.__tablename__ in Base.metadata.tables
    )
except ImportError as e:
    logger.warning("[Database] Could not import library models: %s", e)
except Exception as e:
    logger.warning("[Database] Error registering library models: %s", e, exc_info=True)

try:
    from models.domain.gewe_message import GeweMessage
    _ = GeweMessage.__tablename__
    logger.debug("[Database] Gewe message models imported and registered for migrations")
except ImportError as e:
    logger.debug("[Database] Could not import gewe message models: %s", e)
except Exception as e:
    logger.debug("[Database] Error registering gewe message models: %s", e)

try:
    from models.domain.gewe_contact import GeweContact
    _ = GeweContact.__tablename__
    logger.debug("[Database] Gewe contact models imported and registered for migrations")
except ImportError as e:
    logger.debug("[Database] Could not import gewe contact models: %s", e)
except Exception as e:
    logger.debug("[Database] Error registering gewe contact models: %s", e)

try:
    from models.domain.gewe_group_member import GeweGroupMember
    _ = GeweGroupMember.__tablename__
    logger.debug("[Database] Gewe group member models imported and registered for migrations")
except ImportError as e:
    logger.debug("[Database] Could not import gewe group member models: %s", e)
except Exception as e:
    logger.debug("[Database] Error registering gewe group member models: %s", e)

# Ensure data directory exists for database files
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)


# Database URL from environment variable
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://mindgraph_user:mindgraph_password@localhost:5432/mindgraph")

# Create SQLAlchemy engine with proper pool configuration
# PostgreSQL/MySQL pool configuration for production workloads
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
    
    # Verify LibraryBookmark is registered (explicit check)
    try:
        from models.domain.library import LibraryBookmark
        bookmark_table_name = LibraryBookmark.__tablename__
        if bookmark_table_name not in expected_tables:
            logger.warning(
                "[Database] LibraryBookmark table '%s' is NOT registered in Base.metadata!",
                bookmark_table_name
            )
        else:
            logger.debug(
                "[Database] LibraryBookmark table '%s' is registered in Base.metadata",
                bookmark_table_name
            )
    except Exception as e:
        logger.warning(
            "[Database] Could not verify LibraryBookmark registration: %s",
            e
        )
    
    # Log registered tables for debugging
    logger.debug(
        "[Database] Expected tables in Base.metadata (%d): %s",
        len(expected_tables),
        ', '.join(sorted(expected_tables))
    )
    logger.debug(
        "[Database] Existing tables in database (%d): %s",
        len(existing_tables),
        ', '.join(sorted(existing_tables))
    )

    # Determine which tables need to be created
    missing_tables = expected_tables - existing_tables

    if missing_tables:
        missing_tables_sorted = ', '.join(sorted(missing_tables))
        logger.debug(
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
            logger.debug("Database tables created/verified")
        except (OperationalError, ProgrammingError) as e:
            # Fallback: Handle edge cases where inspector and SQLAlchemy disagree
            # This can happen if table/index was created between inspector check and create_all call
            # ProgrammingError catches duplicate table/index errors (e.g., psycopg2.errors.DuplicateTable)
            # SAFETY: We only catch "already exists" errors - genuine errors are re-raised
            error_msg = str(e).lower()
            duplicate_conditions = (
                "already exists" in error_msg or
                ("table" in error_msg and "exists" in error_msg) or
                ("duplicate" in error_msg and (
                    "table" in error_msg or
                    "index" in error_msg or
                    "relation" in error_msg
                ))
            )
            if duplicate_conditions:
                logger.debug("Table/index creation conflict resolved (already exists): %s", e)
                logger.debug("Database tables verified (already exist)")
            else:
                # Re-raise genuine errors (syntax, permissions, corruption, etc.)
                # This ensures we don't silently ignore real database problems
                logger.error("Database initialization error: %s", e)
                # Send critical alert for database errors during initialization
                if CriticalAlertService is not None:
                    try:
                        error_msg_lower = str(e).lower()
                        if "corrupt" in error_msg_lower or "integrity" in error_msg_lower:
                            details = (
                                "Database may be corrupted or have integrity issues. "
                                "Check database file and permissions."
                            )
                            CriticalAlertService.send_startup_failure_alert_sync(
                                component="Database",
                                error_message=f"Database error during initialization: {str(e)}",
                                details=details
                            )
                    except Exception as alert_error:
                        logger.error("Failed to send database error alert: %s", alert_error)
                raise
    else:
        logger.debug("All database tables already exist - skipping creation")

    # Step 2: Run automatic migrations (add missing columns)
    try:
        migration_result = run_migrations()
        if migration_result:
            logger.debug("Database schema migration completed")
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
            logger.error(
                "[Database] Database connection failed after recovery attempt: %s",
                e
            )
            # Try one more time with a short delay
            time.sleep(0.1)
            try:
                with engine.connect() as conn:
                    result = conn.execute(text("SELECT 1"))
                    result.fetchone()
                    logger.debug("[Database] Database connection verified after retry")
            except Exception as retry_error:
                logger.error(
                    "[Database] Database recovery failed: %s",
                    retry_error
                )
                return False

        logger.debug("[Database] Recovery from kill -9 scenario completed successfully")
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
    engine.dispose()
    logger.info("Database connections closed")
