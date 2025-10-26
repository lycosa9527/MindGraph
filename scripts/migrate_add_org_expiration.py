"""
Database Migration: Add expiration and active status to organizations
Author: MindSpring Team

This script adds the expires_at and is_active columns to the organizations table
for existing databases that don't have these fields yet.

Run this script once after updating the code:
    python scripts/migrate_add_org_expiration.py
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import inspect, text
from config.database import get_db, engine
from models.auth import Organization

def check_column_exists(table_name, column_name):
    """Check if a column exists in a table"""
    inspector = inspect(engine)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns

def migrate():
    """Add expires_at and is_active columns if they don't exist"""
    print("🔍 Checking organization table schema...")
    
    db = next(get_db())
    try:
        # Check if expires_at column exists
        if not check_column_exists('organizations', 'expires_at'):
            print("➕ Adding expires_at column...")
            db.execute(text("ALTER TABLE organizations ADD COLUMN expires_at DATETIME"))
            db.commit()
            print("✅ expires_at column added successfully")
        else:
            print("✓ expires_at column already exists")
        
        # Check if is_active column exists
        if not check_column_exists('organizations', 'is_active'):
            print("➕ Adding is_active column...")
            db.execute(text("ALTER TABLE organizations ADD COLUMN is_active BOOLEAN DEFAULT 1"))
            db.commit()
            print("✅ is_active column added successfully")
        else:
            print("✓ is_active column already exists")
        
        print("\n✅ Migration completed successfully!")
        print("All organizations are set to active by default.")
        print("You can now manage expiration dates through the admin panel.")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    print("=" * 60)
    print("Database Migration: Organization Expiration Management")
    print("=" * 60)
    migrate()

