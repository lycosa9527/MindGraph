#!/usr/bin/env python3
"""
Cleanup Script: Remove Corrupted Demo Users
Author: lycosa9527
Made by: MindSpring Team

Run this script if you're experiencing demo login issues due to corrupted demo users.
This will delete all demo users from the database, allowing fresh ones to be created.
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.database import SessionLocal
from models.auth import User
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s | %(message)s')
logger = logging.getLogger(__name__)

def cleanup_demo_users():
    """Remove all demo users from database"""
    db = SessionLocal()
    try:
        # Find all demo users
        demo_users = db.query(User).filter(User.phone.like('demo%@system.com')).all()
        
        if not demo_users:
            logger.info("✓ No demo users found in database")
            return True
        
        logger.info(f"Found {len(demo_users)} demo user(s):")
        for user in demo_users:
            logger.info(f"  - {user.phone} (ID: {user.id})")
        
        # Ask for confirmation (with default to yes for quick fix)
        print("\n⚠️  This will DELETE all demo users from the database.")
        print("They will be automatically recreated on next demo login.")
        response = input("\nProceed with deletion? (yes/no) [yes]: ").strip().lower()
        
        if not response:
            response = 'yes'  # Default to yes
        
        if response not in ['yes', 'y']:
            logger.info("Cleanup cancelled by user")
            return False
        
        # Delete demo users
        count = 0
        for user in demo_users:
            db.delete(user)
            count += 1
            logger.info(f"Deleted: {user.phone}")
        
        db.commit()
        logger.info(f"\n✓ Successfully deleted {count} demo user(s)")
        logger.info("Demo users will be recreated automatically on next login")
        return True
        
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Cleanup failed: {e}")
        return False
    finally:
        db.close()

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("Demo User Cleanup Script")
    logger.info("=" * 60)
    success = cleanup_demo_users()
    sys.exit(0 if success else 1)

