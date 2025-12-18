#!/usr/bin/env python3
"""
Test script for COS backup functionality.

This script triggers a manual backup and uploads it to COS for testing.
Uses configuration from .env file.

Usage:
    python scripts/test_cos_backup.py
"""

import os
import sys
import asyncio
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Setup logging before importing modules
# Fix Windows encoding issues
import io
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)

logger = logging.getLogger(__name__)

# Load environment variables
from dotenv import load_dotenv
from utils.env_utils import ensure_utf8_env_file

# Ensure .env file is UTF-8 encoded
ensure_utf8_env_file()
load_dotenv()

# Import backup functions after environment is loaded
from services.backup_scheduler import (
    run_backup_now,
    get_backup_status,
    list_cos_backups,
    COS_BACKUP_ENABLED,
    COS_BUCKET,
    COS_REGION,
    COS_KEY_PREFIX
)


async def test_backup():
    """Test backup functionality."""
    print("=" * 60)
    print("Backup Test Script")
    print("=" * 60)
    print()
    
    # Ensure we're running as worker 0 (required for backup)
    os.environ['UVICORN_WORKER_ID'] = '0'
    print("[INFO] Set UVICORN_WORKER_ID=0 for backup test")
    print()
    
    # Check configuration
    print("Configuration Check:")
    print(f"  COS_BACKUP_ENABLED: {COS_BACKUP_ENABLED}")
    print(f"  COS_BUCKET: {COS_BUCKET}")
    print(f"  COS_REGION: {COS_REGION}")
    print(f"  COS_KEY_PREFIX: {COS_KEY_PREFIX}")
    print()
    
    if not COS_BACKUP_ENABLED:
        print("[INFO] COS backup is disabled - will test local backup only")
        print("   Set COS_BACKUP_ENABLED=true to enable COS upload")
    elif not COS_BUCKET:
        print("[WARNING] COS_BUCKET is not configured - will test local backup only")
        print("   Set COS_BUCKET=your-bucket-appid in .env file to enable COS upload")
    
    # Check current backup status
    print("Current Backup Status:")
    status = get_backup_status()
    print(f"  Local backups: {len(status.get('backups', []))}")
    if status.get('backups'):
        print("  Recent local backups:")
        for backup in status['backups'][:3]:
            print(f"    - {backup['filename']} ({backup['size_mb']} MB)")
    print()
    
    # List existing COS backups (if enabled)
    if COS_BACKUP_ENABLED and COS_BUCKET:
        print("Existing COS Backups:")
        cos_backups = list_cos_backups()
        print(f"  Found {len(cos_backups)} backup(s) in COS")
        if cos_backups:
            print("  Recent COS backups:")
            for backup in cos_backups[:5]:
                # Handle size as int or string
                size = int(backup['size']) if isinstance(backup['size'], str) else backup['size']
                size_mb = size / (1024 * 1024)
                print(f"    - {backup['key']} ({size_mb:.2f} MB)")
        else:
            print("  No backups found in COS")
        print()
    
    # Trigger backup
    print("Triggering backup...")
    print("-" * 60)
    try:
        success = await run_backup_now()
        
        if success:
            print()
            print("[SUCCESS] Backup completed successfully!")
            print()
            
            # Check updated status
            print("Updated Backup Status:")
            status = get_backup_status()
            print(f"  Local backups: {len(status.get('backups', []))}")
            if status.get('backups'):
                latest = status['backups'][0]
                print(f"  Latest backup: {latest['filename']} ({latest['size_mb']} MB)")
            print()
            
            # List updated COS backups (if enabled)
            if COS_BACKUP_ENABLED and COS_BUCKET:
                print("Updated COS Backups:")
                cos_backups = list_cos_backups()
                print(f"  Found {len(cos_backups)} backup(s) in COS")
                if cos_backups:
                    print("  Recent COS backups:")
                    for backup in cos_backups[:5]:
                        # Handle size as int or string
                        size = int(backup['size']) if isinstance(backup['size'], str) else backup['size']
                        size_mb = size / (1024 * 1024)
                        print(f"    - {backup['key']} ({size_mb:.2f} MB)")
            
            return True
        else:
            print()
            print("[ERROR] Backup failed!")
            print("   Check logs above for error details")
            return False
            
    except Exception as e:
        print()
        print(f"[ERROR] Backup failed with exception: {e}")
        logger.exception("Backup test failed")
        return False


if __name__ == "__main__":
    try:
        success = asyncio.run(test_backup())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n[WARNING] Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n[ERROR] Test script error: {e}")
        logger.exception("Test script failed")
        sys.exit(1)

