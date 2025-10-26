"""
Database Backup Script for MindGraph
Author: MindSpring Team

Creates timestamped backups of the database and critical configuration files.
Run this regularly or set up as a cron job.

Usage:
    python scripts/backup_database.py
"""

import shutil
import os
from datetime import datetime
from pathlib import Path

# Configuration
BACKUP_DIR = Path("backups")
DATABASE_FILE = Path("mindgraph.db")
ENV_FILE = Path(".env")

def create_backup():
    """Create timestamped backup of database and config"""
    
    # Create backup directory if it doesn't exist
    BACKUP_DIR.mkdir(exist_ok=True)
    
    # Generate timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_subdir = BACKUP_DIR / f"backup_{timestamp}"
    backup_subdir.mkdir(exist_ok=True)
    
    print(f"📦 Creating backup: {backup_subdir}")
    
    # Backup database
    if DATABASE_FILE.exists():
        shutil.copy2(DATABASE_FILE, backup_subdir / DATABASE_FILE.name)
        size_mb = os.path.getsize(DATABASE_FILE) / (1024 * 1024)
        print(f"✅ Database backed up: {DATABASE_FILE} ({size_mb:.2f} MB)")
    else:
        print(f"⚠️  Database not found: {DATABASE_FILE}")
    
    # Backup .env file (contains JWT secret and API keys)
    if ENV_FILE.exists():
        shutil.copy2(ENV_FILE, backup_subdir / ENV_FILE.name)
        print(f"✅ Environment config backed up: {ENV_FILE}")
    else:
        print(f"⚠️  .env file not found: {ENV_FILE}")
    
    # Create restoration instructions
    readme = backup_subdir / "README.txt"
    readme.write_text(f"""
MindGraph Database Backup
Created: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

RESTORATION INSTRUCTIONS:
========================

If you need to restore this backup:

1. Stop the MindGraph server

2. Copy the database file:
   cp {DATABASE_FILE} ./

3. Copy the .env file:
   cp {ENV_FILE} ./

4. Restart the server:
   python run_server.py

IMPORTANT:
- The .env file contains your JWT_SECRET_KEY
- If you use a different JWT_SECRET_KEY, users will need to log in again
- All passwords are bcrypt-hashed and will work with any secret key
- User data, organizations, and API keys are stored in the database

For questions, contact: MindSpring Team
""")
    print(f"✅ Restoration instructions: {readme}")
    
    print(f"\n🎉 Backup completed successfully!")
    print(f"📁 Location: {backup_subdir.absolute()}")
    
    # Clean up old backups (keep last 10)
    cleanup_old_backups()

def cleanup_old_backups(keep=10):
    """Remove old backups, keeping only the most recent ones"""
    backups = sorted(BACKUP_DIR.glob("backup_*"), key=lambda x: x.stat().st_mtime, reverse=True)
    
    if len(backups) > keep:
        for old_backup in backups[keep:]:
            print(f"🗑️  Removing old backup: {old_backup.name}")
            shutil.rmtree(old_backup)

if __name__ == "__main__":
    print("=" * 60)
    print("MindGraph Database Backup Tool")
    print("=" * 60)
    create_backup()

