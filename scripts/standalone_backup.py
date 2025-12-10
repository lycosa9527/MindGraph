#!/usr/bin/env python3
"""
Standalone Database Backup Script for MindGraph
===============================================

This script can be used independently on any server to safely backup
a SQLite database in WAL mode. It doesn't require the full MindGraph
codebase - just Python 3.7+ with sqlite3.

Usage:
    python3 standalone_backup.py [database_path] [backup_path]

Example:
    python3 standalone_backup.py /data/mindgraph.db /backup/mindgraph.db.backup
"""

import sqlite3
import sys
from pathlib import Path
from datetime import datetime

def backup_database_safely(source_db_path, backup_db_path):
    """
    Safely backup SQLite database using SQLite's backup API.
    This properly handles WAL mode by automatically checkpointing
    and copying all committed data.
    
    Args:
        source_db_path: Path to source database file
        backup_db_path: Path to backup database file
        
    Returns:
        True if backup succeeded, False otherwise
    """
    source_conn = None
    backup_conn = None
    
    try:
        print(f"Connecting to source database: {source_db_path}")
        source_conn = sqlite3.connect(str(source_db_path), timeout=30.0)
        
        # Remove existing backup file if it exists
        backup_path = Path(backup_db_path)
        if backup_path.exists():
            print(f"Removing existing backup file: {backup_db_path}")
            backup_path.unlink()
        
        print(f"Creating backup database: {backup_db_path}")
        backup_conn = sqlite3.connect(str(backup_db_path), timeout=30.0)
        
        print("Starting backup (this may take a while for large databases)...")
        # Use SQLite backup API - this handles WAL mode correctly
        # It automatically checkpoints WAL and copies all committed data
        backup = source_conn.backup(backup_conn)
        backup.step(-1)  # -1 means copy all pages
        backup.finish()
        
        # Verify backup file was created and has content
        backup_path = Path(backup_db_path)
        if not backup_path.exists() or backup_path.stat().st_size == 0:
            print("ERROR: Backup file was not created or is empty")
            return False
        
        size_mb = backup_path.stat().st_size / (1024 * 1024)
        print(f"SUCCESS: Backup completed successfully ({size_mb:.2f} MB)")
        print(f"Backup file: {backup_db_path}")
        return True
        
    except sqlite3.Error as e:
        print(f"ERROR: SQLite backup error: {e}")
        # Clean up partial backup file
        try:
            backup_path = Path(backup_db_path)
            if backup_path.exists():
                backup_path.unlink()
                print("Cleaned up partial backup file")
        except Exception as cleanup_error:
            print(f"WARNING: Could not remove partial backup file: {cleanup_error}")
        return False
    except Exception as e:
        print(f"ERROR: Unexpected error during backup: {e}")
        # Clean up partial backup file
        try:
            backup_path = Path(backup_db_path)
            if backup_path.exists():
                backup_path.unlink()
                print("Cleaned up partial backup file")
        except Exception as cleanup_error:
            print(f"WARNING: Could not remove partial backup file: {cleanup_error}")
        return False
    finally:
        # Ensure connections are always closed
        if backup_conn:
            try:
                backup_conn.close()
            except Exception:
                pass
        if source_conn:
            try:
                source_conn.close()
            except Exception:
                pass


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 standalone_backup.py <source_db_path> [backup_db_path]")
        print("\nExamples:")
        print("  python3 standalone_backup.py /data/mindgraph.db")
        print("  python3 standalone_backup.py /data/mindgraph.db /backup/mindgraph.db.backup")
        sys.exit(1)
    
    source_db = sys.argv[1]
    
    # Generate backup path if not provided
    if len(sys.argv) >= 3:
        backup_db = sys.argv[2]
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        source_path = Path(source_db)
        backup_db = str(source_path.parent / f"{source_path.name}.backup_{timestamp}")
    
    print("=" * 60)
    print("MindGraph Standalone Database Backup Tool")
    print("=" * 60)
    print()
    
    # Check if source database exists
    if not Path(source_db).exists():
        print(f"ERROR: Source database not found: {source_db}")
        sys.exit(1)
    
    # Create backup directory if needed
    backup_path = Path(backup_db)
    try:
        backup_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"ERROR: Could not create backup directory: {e}")
        sys.exit(1)
    
    # Perform backup
    success = backup_database_safely(source_db, backup_db)
    
    if success:
        print()
        print("=" * 60)
        print("Backup completed successfully!")
        print("=" * 60)
        print(f"\nIMPORTANT: The backup file is a standalone database.")
        print("You do NOT need to copy .wal or .shm files.")
        print("The backup includes all committed data from WAL mode.")
        sys.exit(0)
    else:
        print()
        print("=" * 60)
        print("Backup failed!")
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()

