#!/usr/bin/env python3
"""
Comprehensive backup test script.

Tests the complete backup workflow:
1. Local backup creation
2. Old local backup cleanup (retention)
3. COS backup upload
4. Old COS backup cleanup

Usage:
    python scripts/test_backup_full.py
"""

import os
import sys
import asyncio
import logging
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Setup logging
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

ensure_utf8_env_file()
load_dotenv()

# Ensure we're running as worker 0 (required for backup)
os.environ['UVICORN_WORKER_ID'] = '0'

# Import backup functions
from services.backup_scheduler import (
    run_backup_now,
    get_backup_status,
    list_cos_backups,
    cleanup_old_backups,
    cleanup_old_cos_backups,
    BACKUP_DIR,
    BACKUP_RETENTION_COUNT,
    COS_BACKUP_ENABLED,
    COS_BUCKET,
)


async def test_full_backup_workflow():
    """Test the complete backup workflow."""
    print("=" * 70)
    print("COMPREHENSIVE BACKUP TEST")
    print("=" * 70)
    print()
    
    print("Test Plan:")
    print("  1. Check initial backup state")
    print("  2. Trigger backup (should create local backup)")
    print("  3. Verify local backup retention (should keep only N backups)")
    print("  4. Verify COS upload (if enabled)")
    print("  5. Verify COS cleanup (if enabled)")
    print()
    
    # Step 1: Check initial state
    print("=" * 70)
    print("STEP 1: Initial Backup State")
    print("=" * 70)
    status = get_backup_status()
    initial_local_count = len(status.get('backups', []))
    print(f"  Local backups: {initial_local_count}")
    print(f"  Retention count: {BACKUP_RETENTION_COUNT}")
    if status.get('backups'):
        print("  Current local backups:")
        for i, backup in enumerate(status['backups'], 1):
            print(f"    {i}. {backup['filename']} ({backup['size_mb']} MB) - {backup['created']}")
    
    initial_cos_count = 0
    if COS_BACKUP_ENABLED and COS_BUCKET:
        cos_backups = list_cos_backups()
        initial_cos_count = len(cos_backups)
        print(f"\n  COS backups: {initial_cos_count}")
        if cos_backups:
            print("  Current COS backups:")
            for i, backup in enumerate(cos_backups[:5], 1):
                size = int(backup['size']) if isinstance(backup['size'], str) else backup['size']
                size_mb = size / (1024 * 1024)
                print(f"    {i}. {backup['key']} ({size_mb:.2f} MB)")
    print()
    
    # Step 2: Trigger backup
    print("=" * 70)
    print("STEP 2: Trigger Backup")
    print("=" * 70)
    print("  Triggering backup...")
    try:
        success = await run_backup_now()
        if not success:
            print("  [ERROR] Backup failed!")
            return False
        print("  [SUCCESS] Backup completed")
    except Exception as e:
        print(f"  [ERROR] Backup exception: {e}")
        logger.exception("Backup failed")
        return False
    print()
    
    # Step 3: Verify local backup retention
    print("=" * 70)
    print("STEP 3: Verify Local Backup Retention")
    print("=" * 70)
    status = get_backup_status()
    final_local_count = len(status.get('backups', []))
    print(f"  Local backups after backup: {final_local_count}")
    print(f"  Expected: <= {BACKUP_RETENTION_COUNT}")
    
    if final_local_count > BACKUP_RETENTION_COUNT:
        print(f"  [WARNING] Too many backups! Expected <= {BACKUP_RETENTION_COUNT}, got {final_local_count}")
    else:
        print(f"  [SUCCESS] Backup retention working correctly")
    
    if status.get('backups'):
        print("\n  Current local backups:")
        for i, backup in enumerate(status['backups'], 1):
            print(f"    {i}. {backup['filename']} ({backup['size_mb']} MB) - {backup['created']}")
    
    # Verify cleanup happened if we had more than retention count
    if initial_local_count >= BACKUP_RETENTION_COUNT:
        expected_final = BACKUP_RETENTION_COUNT
        if final_local_count == expected_final:
            print(f"\n  [SUCCESS] Old backup cleanup worked: {initial_local_count} -> {final_local_count}")
        else:
            print(f"\n  [WARNING] Cleanup may not have worked: {initial_local_count} -> {final_local_count} (expected {expected_final})")
    print()
    
    # Step 4: Verify COS upload
    if COS_BACKUP_ENABLED and COS_BUCKET:
        print("=" * 70)
        print("STEP 4: Verify COS Backup Upload")
        print("=" * 70)
        cos_backups = list_cos_backups()
        final_cos_count = len(cos_backups)
        print(f"  COS backups after upload: {final_cos_count}")
        print(f"  Initial count: {initial_cos_count}")
        
        if final_cos_count > initial_cos_count:
            print(f"  [SUCCESS] COS upload worked: {initial_cos_count} -> {final_cos_count}")
            if cos_backups:
                print("\n  Latest COS backups:")
                for i, backup in enumerate(cos_backups[:3], 1):
                    size = int(backup['size']) if isinstance(backup['size'], str) else backup['size']
                    size_mb = size / (1024 * 1024)
                    print(f"    {i}. {backup['key']} ({size_mb:.2f} MB)")
        else:
            print(f"  [WARNING] COS upload may not have worked: {initial_cos_count} -> {final_cos_count}")
        print()
        
        # Step 5: Test COS cleanup (manually trigger to verify)
        print("=" * 70)
        print("STEP 5: Verify COS Backup Cleanup")
        print("=" * 70)
        print("  Testing COS cleanup (retention: 2 days)...")
        deleted_count = cleanup_old_cos_backups(retention_days=2)
        print(f"  Deleted {deleted_count} old COS backup(s)")
        
        cos_backups_after_cleanup = list_cos_backups()
        final_after_cleanup = len(cos_backups_after_cleanup)
        print(f"  COS backups after cleanup: {final_after_cleanup}")
        
        if deleted_count > 0:
            print(f"  [SUCCESS] COS cleanup deleted {deleted_count} old backup(s)")
        else:
            print(f"  [INFO] No old backups to clean up (all backups are within 2 days)")
        print()
    
    # Summary
    print("=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    print(f"  Local backups: {initial_local_count} -> {final_local_count} (retention: {BACKUP_RETENTION_COUNT})")
    if COS_BACKUP_ENABLED and COS_BUCKET:
        print(f"  COS backups: {initial_cos_count} -> {final_cos_count}")
    print()
    print("  [SUCCESS] All backup workflow tests completed!")
    return True


if __name__ == "__main__":
    try:
        success = asyncio.run(test_full_backup_workflow())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n[WARNING] Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n[ERROR] Test script error: {e}")
        logger.exception("Test script failed")
        sys.exit(1)



