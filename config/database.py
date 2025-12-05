"""
Database Configuration for MindGraph Authentication
Author: lycosa9527
Made by: MindSpring Team

SQLAlchemy database setup and session management.
"""

import os
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

# Database URL from environment variable
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./mindgraph.db")

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

