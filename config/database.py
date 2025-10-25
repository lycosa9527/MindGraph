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
    # Create all tables
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully")
    
    # Seed demo organizations
    db = SessionLocal()
    try:
        # Check if organizations already exist
        if db.query(Organization).count() == 0:
            demo_orgs = [
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
            
            db.add_all(demo_orgs)
            db.commit()
            logger.info(f"Seeded {len(demo_orgs)} demo organizations")
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

