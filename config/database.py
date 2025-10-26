"""
Database Configuration for MindGraph Authentication
Author: lycosa9527
Made by: MindSpring Team

SQLAlchemy database setup and session management.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from models.auth import Base, Organization
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Database URL from environment variable
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./mindgraph.db")

# Create SQLAlchemy engine
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    echo=False  # Set to True for SQL query logging
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """
    Initialize database: create tables and seed demo data
    """
    # Import here to avoid circular dependency
    from utils.auth import load_invitation_codes
    from sqlalchemy import inspect, text
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully")
    
    # Migration: Add expires_at and is_active columns if they don't exist
    inspector = inspect(engine)
    columns = [col['name'] for col in inspector.get_columns('organizations')]
    
    db = SessionLocal()
    try:
        if 'expires_at' not in columns:
            logger.info("Adding expires_at column to organizations table...")
            db.execute(text("ALTER TABLE organizations ADD COLUMN expires_at DATETIME"))
            db.commit()
            logger.info("expires_at column added successfully")
        
        if 'is_active' not in columns:
            logger.info("Adding is_active column to organizations table...")
            db.execute(text("ALTER TABLE organizations ADD COLUMN is_active BOOLEAN DEFAULT 1"))
            db.commit()
            logger.info("is_active column added successfully")
    except Exception as e:
        logger.error(f"Migration error: {e}")
        db.rollback()
    finally:
        db.close()
    
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

